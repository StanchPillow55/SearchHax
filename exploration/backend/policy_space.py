"""Record focus policy coordinates onto a checkpoint.

The integrated evidence space reads this snapshot. It does not rank again.
Coordinates are selection scores: intent alignment, novelty, and
unresolved-question alignment. They are not factual confidence, not user
knowledge, and not the retrieval-attention score.
"""

from __future__ import annotations

from datetime import date, datetime

from exploration.backend.attention import REFERENCE_DATE
from focus.focus_attention import FocusAttentionModel, Passage
from shared.contracts import ExplorationExport


def record_policy_space(export: ExplorationExport) -> list[dict]:
    """Score the export's recorded candidates once. Does not modify the export."""
    investigation_id = export.investigation.id
    branch_raw = export.investigation.metadata.get("branch_id")
    branch_id = branch_raw or f"root:{investigation_id}"
    content_by_document: dict[str, str] = {}
    for version in export.document_versions:
        content_by_document.setdefault(version.document_id, version.content)
    passages: list[Passage] = []
    candidates = {}
    for candidate in export.candidates:
        stored = content_by_document.get(candidate.document_id or "") or ""
        text = (stored or candidate.snippet or candidate.title or "").strip()
        if not text:
            continue
        passages.append(
            Passage(
                id=candidate.id,
                text=text,
                url=candidate.url,
                title=candidate.title,
                providers=tuple(candidate.providers),
                published_at=_published(candidate.publish_date),
            )
        )
        candidates[candidate.id] = (candidate, "document" if stored.strip() else ("snippet" if candidate.snippet else "title"))
    if not passages or not export.investigation.question.strip():
        return []
    model = FocusAttentionModel(
        export.investigation.question,
        unresolved_questions=tuple(question.text for question in export.unresolved_questions),
        now=REFERENCE_DATE,
    )
    rows = []
    for rank, decision in enumerate(model.rank(passages)):
        candidate, source = candidates[decision.passage.id]
        knowledge = candidate.knowledge_value
        excerpt = candidate.snippet.strip() or decision.passage.text[:280]
        rows.append(
            {
                "evidence_id": candidate.id,
                "investigation_id": investigation_id,
                "branch_id": branch_id,
                "document_id": candidate.document_id,
                "url": candidate.url,
                "title": candidate.title,
                "passage": excerpt[:400],
                "intent_alignment": decision.score.relevance,
                "novelty": decision.score.novelty,
                "unresolved_alignment": decision.score.graph_gap,
                "action": decision.action,
                "reason": decision.reason,
                "policy_rank": rank,
                "attention_score": candidate.attention.score,
                "attention_relevance": candidate.attention.R,
                "attention_gap": candidate.attention.G,
                "knowledge_value_score": knowledge.score if knowledge is not None else None,
                "knowledge_value_novelty": knowledge.N if knowledge is not None else None,
                "bridge_trigger": knowledge.bridge_trigger if knowledge is not None else None,
                "scored_text_source": source,
                "coordinate_source": "focus_policy_checkpoint",
                "granularity": "document",
            }
        )
    return rows


def record_passage_space(export: ExplorationExport) -> list[dict]:
    """Per-passage coordinates (additive, 1.1.0): one point per stored evidence span.

    Stored separately (checkpoint ``state_json.policy_space_passages``) so readers of the
    document-level ``policy_space`` are unchanged. The text scored is exactly the stored span
    text, so a passage selected in the trace maps to its own point.
    """
    investigation_id = export.investigation.id
    branch_id = export.investigation.metadata.get("branch_id") or f"root:{investigation_id}"
    if not export.investigation.question.strip():
        return []
    documents = {document.id: document for document in export.documents}
    passages: list[Passage] = []
    spans = {}
    for span in export.evidence_spans:
        text = (span.text or "").strip()
        document = documents.get(span.document_id)
        if not text or document is None:
            continue
        # url="" makes the ranker key on the span id: passages from one page are separate points
        # here (the ranker otherwise merges same-URL passages into one source). The row still
        # records the document URL.
        passages.append(Passage(id=span.id, text=text, url="", title=document.title))
        spans[span.id] = (span, document)
    if not passages:
        return []
    model = FocusAttentionModel(
        export.investigation.question,
        unresolved_questions=tuple(question.text for question in export.unresolved_questions),
        now=REFERENCE_DATE,
    )
    rows = []
    for rank, decision in enumerate(model.rank(passages)):
        span, document = spans[decision.passage.id]
        rows.append(
            {
                "evidence_id": span.id,
                "span_id": span.id,
                "investigation_id": investigation_id,
                "branch_id": branch_id,
                "document_id": span.document_id,
                "url": document.canonical_url,
                "title": document.title,
                "passage": span.text[:400],
                "intent_alignment": decision.score.relevance,
                "novelty": decision.score.novelty,
                "unresolved_alignment": decision.score.graph_gap,
                "action": decision.action,
                "reason": decision.reason,
                "policy_rank": rank,
                "scored_text_source": "evidence_span",
                "coordinate_source": "focus_policy_checkpoint_passage",
                "granularity": "passage",
            }
        )
    return rows


def _published(value: str | None) -> date | None:
    if not value:
        return None
    text = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text).date()
    except ValueError:
        pass
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None
