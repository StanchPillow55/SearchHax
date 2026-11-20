"""Offline profile investigation. No retrieval, no provider, and no LLM call.

The original question stays the fixture question. Profile priors stay in the
profile snapshot and are not stored as sourced web evidence. Query attention
and knowledge value rank the same passages and are both persisted.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from shared.contracts import (
    Document,
    DocumentVersion,
    EvidenceCandidate,
    ExplorationExport,
    ResearchProfile,
    SourceProvenance,
    UnresolvedQuestion,
)

from exploration.backend.attention import score_passage
from exploration.backend.checkpoints import save_checkpoint
from exploration.backend.config import profile_fixture_dir
from exploration.backend.extraction import relationships_from_llm_payload
from exploration.backend.ids import content_hash, stable_id
from exploration.backend.knowledge_value import occurring_interests, score_knowledge_value
from exploration.backend.retrieval import normalize_url

SAMPLE_NOTE = (
    "One fixed corpus. This is not a claim about Tavily /research or a general LLM. "
    "Iterative search is not the claim. "
    "This is not proof that FrontierGraph outperforms an LLM with equivalent memory."
)


@dataclass(frozen=True)
class ProfileDocument:
    fixture_id: str
    url: str
    title: str
    publish_date: str
    content: str
    candidate: dict | None


def load_profile_fixture(directory: Path | None = None) -> tuple[ResearchProfile, str, list[ProfileDocument]]:
    root = directory or profile_fixture_dir()
    raw = json.loads((root / "ai_infrastructure.json").read_text(encoding="utf-8"))
    profile = ResearchProfile.model_validate(raw)
    question = str(raw["question"]).strip()
    documents: list[ProfileDocument] = []
    for item in raw["documents"]:
        documents.append(
            ProfileDocument(
                fixture_id=item["id"],
                url=item["url"],
                title=item["title"],
                publish_date=item["publish_date"],
                content=(root / item["file"]).read_text(encoding="utf-8"),
                candidate=item.get("candidate"),
            )
        )
    return profile, question, documents


def execute_profile(orchestrator, directory: Path | None = None, *, bridges=None) -> ExplorationExport:
    profile, question, documents = load_profile_fixture(directory)
    started = datetime.now(timezone.utc).timestamp()
    investigation = orchestrator.create(question, mode="profile")
    investigation.usage.configuration = "profile"
    investigation.usage.providers_used = ["fixture"]
    investigation.usage.corpus_documents = len(documents)
    investigation.metadata["mode"] = "profile"
    investigation.metadata["extraction_origin"] = "deterministic_fixture"
    investigation.metadata["llm_relationships"] = 0
    investigation.metadata["profile_snapshot"] = profile.model_dump(mode="json")
    investigation.metadata["sample_note"] = SAMPLE_NOTE

    stored_documents: list[Document] = []
    versions: list[DocumentVersion] = []
    provenance: list[SourceProvenance] = []
    candidates: list[EvidenceCandidate] = []
    rows: list[dict] = []
    for item in documents:
        canonical = normalize_url(item.url)
        digest = content_hash(item.content)
        document = Document(
            id=stable_id("doc", investigation.id, item.fixture_id),
            canonical_url=canonical,
            title=item.title,
            origin_id=item.fixture_id,
            providers=["fixture"],
        )
        version = DocumentVersion(
            id=stable_id("ver", document.id, digest),
            document_id=document.id,
            content_hash=digest,
            fetched_at=_now(),
            content=item.content,
            publish_date=item.publish_date,
        )
        attention = score_passage(question, item.content, None, item.publish_date)
        knowledge = score_knowledge_value(item.content, profile, bridges=bridges)
        stored_documents.append(document)
        versions.append(version)
        provenance.append(
            SourceProvenance(
                id=stable_id("prov", document.id, item.fixture_id),
                document_id=document.id,
                provider="fixture",
                providers=["fixture"],
                origin_id=item.fixture_id,
                origin_kind="unknown",
                notes="Local profile-corpus fixture. Not a web fetch and not a profile prior.",
            )
        )
        candidates.append(
            EvidenceCandidate(
                id=stable_id("cand", document.id),
                document_id=document.id,
                url=document.canonical_url,
                title=document.title,
                snippet=item.content[:280].replace("\n", " "),
                providers=["fixture"],
                attention=attention,
                knowledge_value=knowledge,
                publish_date=item.publish_date,
            )
        )
        rows.append(
            {
                "fixture_id": item.fixture_id,
                "document_id": document.id,
                "title": item.title,
                "attention": attention.model_dump(mode="json"),
                "knowledge_value": knowledge.model_dump(mode="json"),
            }
        )

    b0 = sorted(rows, key=lambda row: (-row["attention"]["score"], row["fixture_id"]))
    b3 = sorted(rows, key=lambda row: (-row["knowledge_value"]["score"], row["fixture_id"]))
    same = b0[0]["fixture_id"] == b3[0]["fixture_id"]
    comparison = (
        "B0 and B3 select the same passage."
        if same
        else "B0 ordinary query ranking and B3 knowledge-value ranking select different passages on this fixed corpus."
    )
    by_fixture = {item.fixture_id: item for item in documents}
    selected = by_fixture[b3[0]["fixture_id"]]
    selected_row = next(row for row in rows if row["fixture_id"] == selected.fixture_id)
    discovery, batch = _discovery(
        selected,
        selected_row,
        profile,
        investigation_id=investigation.id,
        question=question,
    )
    entities = []
    claims = []
    relationships = []
    spans = []
    links = []
    if batch is not None:
        entities = list(batch.entities)
        claims = list(batch.claims)
        relationships = list(batch.relationships)
        spans = list(batch.spans)
        links = list(batch.links)
        investigation.usage.rejected_ungrounded_citations += batch.rejected_ungrounded

    unique_facts = []
    known = {(claim.subject.casefold(), claim.predicate.casefold(), claim.object.casefold()) for claim in profile.known_claims}
    for rel in relationships:
        triple = (rel.subject_name.casefold(), rel.predicate.casefold(), rel.object_name.casefold())
        if rel.status == "supported" and triple not in known:
            quote = ""
            for link in links:
                if link.relationship_id == rel.id:
                    span = next((item for item in spans if item.id == link.evidence_span_id), None)
                    quote = span.text if span is not None else ""
                    break
            unique_facts.append(
                {
                    "subject": rel.subject_name,
                    "predicate": rel.predicate,
                    "object": rel.object_name,
                    "fixture_id": selected.fixture_id,
                    "quotation": quote,
                    "origin": "sourced_fixture",
                }
            )
    attestations = [
        {
            "id": claim.id,
            "subject": claim.subject,
            "predicate": claim.predicate,
            "object": claim.object,
            "text": claim.text,
            "origin": "profile_prior",
        }
        for claim in profile.known_claims
    ]
    questions = [
        UnresolvedQuestion(
            id=stable_id("q", investigation.id, interest),
            text=interest,
            importance=0.8,
            missing_evidence=1.0,
            kind="profile_interest",
        )
        for interest in profile.unresolved_interests
    ]
    investigation.metadata["rankings"] = {"B0": b0, "B3": b3}
    investigation.metadata["b0_selected"] = b0[0]["fixture_id"]
    investigation.metadata["b3_selected"] = b3[0]["fixture_id"]
    investigation.metadata["same_passage"] = same
    investigation.metadata["comparison_note"] = comparison
    investigation.metadata["discovery"] = discovery
    investigation.metadata["unique_facts"] = unique_facts
    investigation.metadata["attestations"] = attestations
    investigation.status = "stopped"
    investigation.stop_reason = "unresolved_uncertainty"
    investigation.decision_source = None
    investigation.decision_rationale = discovery.get("reason") or comparison
    investigation.usage.latency_ms = max(0, int((datetime.now(timezone.utc).timestamp() - started) * 1000))
    investigation.updated_at = _now()
    export = ExplorationExport(
        investigation=investigation,
        documents=stored_documents,
        document_versions=versions,
        evidence_spans=spans,
        entities=entities,
        claims=claims,
        relationships=relationships,
        evidence_links=links,
        provenance=provenance,
        unresolved_questions=questions,
        candidates=candidates,
        profile=profile,
    )
    orchestrator._persist(export)
    orchestrator._record_fixture_stages(export, summary_prefix="offline profile corpus")
    save_checkpoint(
        orchestrator.database,
        export,
        step=1,
        summary="Ranked the fixed profile corpus offline with query attention and knowledge value.",
        stop_reason=investigation.stop_reason,
    )
    return orchestrator.graph.load(investigation.id)


def evaluation_from_export(export: ExplorationExport) -> dict:
    meta = export.investigation.metadata
    discovery = meta.get("discovery") or {}
    return {
        "question": export.investigation.question,
        "extraction_origin": meta.get("extraction_origin"),
        "network_calls": export.investigation.usage.network_calls,
        "provider_calls": export.investigation.usage.provider_calls,
        "llm_calls": export.investigation.usage.llm_calls,
        "search_calls": export.investigation.usage.search_calls,
        "b0_order": [row["fixture_id"] for row in meta["rankings"]["B0"]],
        "b3_order": [row["fixture_id"] for row in meta["rankings"]["B3"]],
        "b0_selected": meta["b0_selected"],
        "b3_selected": meta["b3_selected"],
        "same_passage": meta["same_passage"],
        "comparison_note": meta["comparison_note"],
        "rankings": meta["rankings"],
        "surfaced_bridge": {
            "fixture_id": discovery.get("fixture_id"),
            "prior_interest": discovery.get("prior_interest"),
            "quotation": discovery.get("quotation"),
            "bridge_trigger": discovery.get("bridge_trigger"),
            "bridge_terms": discovery.get("bridge_terms") or [],
            "reason": discovery.get("reason"),
            "surfaced": discovery.get("surfaced"),
        },
        "unique_facts": meta.get("unique_facts") or [],
        "attestations": meta.get("attestations") or [],
        "profile_context": meta.get("profile_snapshot"),
        "sample_note": meta.get("sample_note") or SAMPLE_NOTE,
    }


def _discovery(item: ProfileDocument, row: dict, profile: ResearchProfile, *, investigation_id: str, question: str):
    knowledge = row["knowledge_value"]
    del investigation_id
    if knowledge["B"] != 1.0 or not knowledge.get("bridge_trigger"):
        return (
            {
                "surfaced": False,
                "rejected": False,
                "fixture_id": item.fixture_id,
                "status": "not_a_bridge",
                "prior_interest": None,
                "quotation": None,
                "bridge_trigger": knowledge.get("bridge_trigger"),
                "bridge_terms": knowledge.get("bridge_terms") or [],
                "reason": "B3 selected a passage that is not a DOMAIN_BRIDGES bridge. No bridge was surfaced.",
            },
            None,
        )
    candidate = item.candidate or {}
    quote = str(candidate.get("quote") or "")
    subject = str(candidate.get("subject") or "")
    predicate = str(candidate.get("predicate") or "")
    obj = str(candidate.get("object") or "")
    prior = _prior_interest(item.content, profile)
    trigger = knowledge.get("bridge_trigger")
    if not quote or not subject or not predicate or not obj:
        return (
            {
                "surfaced": False,
                "rejected": True,
                "fixture_id": item.fixture_id,
                "status": "rejected",
                "prior_interest": prior,
                "quotation": quote or None,
                "bridge_trigger": trigger,
                "bridge_terms": knowledge.get("bridge_terms") or [],
                "reason": f'Prior interest "{prior}" had no exact quotation to ground, so the discovery was rejected.',
            },
            None,
        )
    document_id = row["document_id"]
    version_id = stable_id("ver", document_id, content_hash(item.content))
    batch = relationships_from_llm_payload(
        {
            "relationships": [
                {
                    "subject": subject,
                    "predicate": predicate,
                    "object": obj,
                    "quote": quote,
                    "kind": "factual",
                }
            ]
        },
        item.content,
        document_id=document_id,
        version_id=version_id,
        version_hash=content_hash(item.content),
        question=question,
        publish_date=item.publish_date,
    )
    supported = [rel for rel in batch.relationships if rel.status == "supported"]
    exact = [span for span in batch.spans if span.quote_valid and span.text == quote and item.content[span.start : span.end] == quote]
    if not supported or not exact:
        return (
            {
                "surfaced": False,
                "rejected": True,
                "fixture_id": item.fixture_id,
                "status": "rejected",
                "prior_interest": prior,
                "quotation": quote,
                "bridge_trigger": trigger,
                "bridge_terms": knowledge.get("bridge_terms") or [],
                "reason": (
                    f'Prior interest "{prior}" is connected by the quotation "{quote}". '
                    "The quotation is not an exact substring of the stored document, so the discovery was rejected."
                ),
            },
            batch,
        )
    reason = (
        f'Prior interest "{prior}" is connected by the quotation "{quote}". '
        f"The {trigger} bridge supplied {', '.join(knowledge.get('bridge_terms') or [])}."
    )
    return (
        {
            "surfaced": True,
            "rejected": False,
            "fixture_id": item.fixture_id,
            "status": "supported",
            "prior_interest": prior,
            "quotation": quote,
            "bridge_trigger": trigger,
            "bridge_terms": knowledge.get("bridge_terms") or [],
            "reason": reason,
        },
        batch,
    )


def _prior_interest(passage: str, profile: ResearchProfile) -> str:
    found = occurring_interests(passage, profile)
    if found:
        return found[0]
    if profile.unresolved_interests:
        return profile.unresolved_interests[0]
    return profile.interests[0] if profile.interests else ""


def _now() -> datetime:
    return datetime.now(timezone.utc)
