"""BranchPoint-style checkpoints stored as SQLite JSON snapshots."""

from __future__ import annotations

from datetime import datetime, timezone

from shared.contracts import Checkpoint, ExplorationExport, StopReason

from exploration.backend.database import Database
from exploration.backend.ids import new_id


def save_checkpoint(
    database: Database,
    export: ExplorationExport,
    *,
    step: int,
    summary: str,
    stop_reason: StopReason | None = None,
) -> Checkpoint:
    state = {
        "question": export.investigation.question,
        "status": export.investigation.status,
        "stop_reason": export.investigation.stop_reason,
        "decision_source": export.investigation.decision_source,
        "decision_rationale": export.investigation.decision_rationale,
        "decision": export.decision.model_dump(mode="json") if export.decision is not None else None,
        "budget": export.investigation.budget.model_dump(mode="json"),
        "usage": export.investigation.usage.model_dump(mode="json"),
        "session_id": export.investigation.session_id,
        "document_ids": [document.id for document in export.documents],
        "version_hashes": [
            {"id": version.id, "document_id": version.document_id, "content_hash": version.content_hash}
            for version in export.document_versions
        ],
        "relationship_status": [
            {"id": rel.id, "status": rel.status, "predicate": rel.predicate, "object_name": rel.object_name}
            for rel in export.relationships
        ],
        "unresolved_questions": [question.model_dump(mode="json") for question in export.unresolved_questions],
        "actions": [action.model_dump(mode="json") for action in export.actions],
        "contradiction_ids": [item.id for item in export.contradictions],
        "origin_ids": [cluster.origin_id for cluster in export.origin_clusters],
    }
    checkpoint = Checkpoint(
        id=new_id("cp"),
        investigation_id=export.investigation.id,
        step=step,
        state_json=state,
        stop_reason=stop_reason if stop_reason is not None else export.investigation.stop_reason,
        created_at=datetime.now(timezone.utc),
        summary=summary,
    )
    database.insert_checkpoint(checkpoint)
    return checkpoint


def list_checkpoints(database: Database, investigation_id: str) -> list[Checkpoint]:
    return database.list_checkpoints(investigation_id)
