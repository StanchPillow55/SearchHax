"""Quotation checks, provenance classification, and cross-document conflicts.

A quotation is valid only when it is an exact substring of the stored document
version. Quotation validity is not semantic support. A sentence can be a real
quotation from a derivative article and still contradict the original source.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from shared.contracts import (
    Claim,
    Contradiction,
    EvidenceLink,
    OriginCluster,
    Relationship,
    SourceProvenance,
    VerificationStatus,
)

from exploration.backend.ids import stable_id

_URL_RE = re.compile(r"https://[^\s)>\]]+")
_WIRE_RE = re.compile(r"LF-PR-\d{4}-\d+")
_PRESS_URL = "https://lumenarc.example/press/2026-03-04-helios-array"
_AMOUNT_PREDICATES = {"raised_amount", "invested_amount"}


@dataclass
class QuoteAssessment:
    valid: bool
    start: int | None
    end: int | None
    note: str = "quotation validity is not semantic support"


def assess_quotation(content: str, quote: str) -> QuoteAssessment:
    if not quote:
        return QuoteAssessment(False, None, None)
    start = content.find(quote)
    if start < 0:
        return QuoteAssessment(False, None, None)
    return QuoteAssessment(True, start, start + len(quote))


def decide_status(content: str, quote: str, subject: str, obj: str) -> tuple[VerificationStatus, QuoteAssessment]:
    """Ignore any status proposed by a model. Grounding decides the status."""
    assessment = assess_quotation(content, quote)
    if not assessment.valid:
        return "insufficient", assessment
    if subject.lower() in quote.lower() and obj.lower() in quote.lower():
        return "supported", assessment
    return "insufficient", assessment


def classify_provenance(
    document_id: str,
    url: str,
    content: str,
    providers: list[str],
) -> SourceProvenance:
    """Group documents that cite the same wire or press URL. Do not treat that as independence."""
    wire_match = _WIRE_RE.search(content)
    wire_id = wire_match.group(0) if wire_match else None
    cited_urls = _URL_RE.findall(content)
    cites_press = any(item.startswith(_PRESS_URL) for item in cited_urls) or _PRESS_URL in content
    if "FOR IMMEDIATE RELEASE" in content and wire_id:
        kind = "original"
        notes = "Original announcement identified by the release marker and wire id."
    elif wire_id or cites_press:
        kind = "derivative"
        notes = "Cites the same wire id or press URL as the original announcement."
    else:
        kind = "unknown"
        notes = "No shared origin indicator found. Lineage is unresolved, not independent."
    provider = providers[0] if providers else None
    return SourceProvenance(
        id=stable_id("prov", document_id, wire_id or url),
        document_id=document_id,
        provider=provider,
        providers=list(providers),
        origin_url=_PRESS_URL if (kind != "unknown" and (cites_press or url.startswith(_PRESS_URL) or wire_id)) else None,
        origin_id=wire_id,
        origin_kind=kind,
        cited_origin_ids=[wire_id] if wire_id else [],
        shared_origin_group=wire_id,
        notes=notes,
    )


def origin_clusters(provenance: list[SourceProvenance]) -> list[OriginCluster]:
    grouped: dict[str, list[SourceProvenance]] = {}
    for item in provenance:
        if not item.shared_origin_group:
            continue
        grouped.setdefault(item.shared_origin_group, []).append(item)
    clusters: list[OriginCluster] = []
    for origin_id, items in grouped.items():
        clusters.append(
            OriginCluster(
                origin_id=origin_id,
                document_ids=[item.document_id for item in items],
                original_document_ids=[item.document_id for item in items if item.origin_kind == "original"],
                derivative_document_ids=[item.document_id for item in items if item.origin_kind == "derivative"],
            )
        )
    return clusters


def reconcile_amount_conflicts(
    relationships: list[Relationship],
    claims: list[Claim],
    links: list[EvidenceLink],
    provenance: list[SourceProvenance],
) -> list[Contradiction]:
    """Mark disagreeing financing amounts. The original's grounded amount stays supported."""
    by_doc = {item.document_id: item for item in provenance}
    claims_by_id = {claim.id: claim for claim in claims}
    links_by_rel: dict[str, list[EvidenceLink]] = {}
    for link in links:
        if link.relationship_id:
            links_by_rel.setdefault(link.relationship_id, []).append(link)

    groups: dict[tuple[str, str], list[Relationship]] = {}
    for rel in relationships:
        if rel.predicate not in _AMOUNT_PREDICATES or rel.status != "supported":
            continue
        groups.setdefault((rel.subject_id, rel.predicate), []).append(rel)

    contradictions: list[Contradiction] = []
    for (_subject_id, predicate), rels in groups.items():
        amounts = {_amount_key(rel.object_name) for rel in rels}
        if len(amounts) <= 1:
            continue
        originals = [
            rel
            for rel in rels
            if by_doc.get(rel.document_id or "", SourceProvenance(id="", document_id="", origin_kind="unknown")).origin_kind
            == "original"
        ]
        reference = _amount_key(originals[0].object_name) if originals else None
        reference_name = originals[0].object_name if originals else ""
        reference_doc = originals[0].document_id or "" if originals else ""
        for rel in rels:
            amount = _amount_key(rel.object_name)
            conflicts = (reference is not None and amount != reference) or reference is None
            if not conflicts:
                continue
            rel.status = "contradicted"
            rel.notes = (
                f"Contradicts the original {predicate} value {reference_name or 'unknown'} "
                f"with {rel.object_name}. The quotation is still an exact substring of the derivative."
            )
            if rel.claim_id and rel.claim_id in claims_by_id:
                claims_by_id[rel.claim_id].status = "contradicted"
            for link in links_by_rel.get(rel.id, []):
                link.semantic_status = "contradicted"
                link.stance = "contradicts"
                # quote_valid stays as stored. Validity is not support.
            contradictions.append(
                Contradiction(
                    id=stable_id("con", rel.id, reference or "none"),
                    subject_name=rel.subject_name,
                    predicate=predicate,
                    supported_object=reference_name,
                    conflicting_object=rel.object_name,
                    original_document_id=reference_doc,
                    conflicting_document_id=rel.document_id or "",
                    conflicting_relationship_id=rel.id,
                    detail=rel.notes,
                )
            )
    return contradictions


def _amount_key(name: str) -> str:
    match = re.search(r"\$\d[\d,]*(?:\.\d+)? (?:million|billion)", name)
    return match.group(0) if match else name.strip().lower()
