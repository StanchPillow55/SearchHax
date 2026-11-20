"""BranchPoint-style checkpoints stored as SQLite JSON snapshots."""

from __future__ import annotations

from datetime import datetime, timezone

from shared.contracts import Checkpoint, ExplorationExport, StopReason

from exploration.backend.database import Database
from exploration.backend.ids import new_id
from exploration.backend.policy_space import record_policy_space


def save_checkpoint(
    database: Database,
    export: ExplorationExport,
    *,
    step: int,
    summary: str,
    stop_reason: StopReason | None = None,
    extra: dict | None = None,
) -> Checkpoint:
    profile = export.profile.model_dump(mode="json") if export.profile is not None else export.investigation.metadata.get("profile_snapshot")
    recorded_stop = stop_reason if stop_reason is not None else export.investigation.stop_reason
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
        "snapshot": {
            "profile": profile,
            "decision": export.decision.model_dump(mode="json") if export.decision is not None else None,
            "documents": [item.model_dump(mode="json") for item in export.documents],
            "document_versions": [item.model_dump(mode="json") for item in export.document_versions],
            "evidence_spans": [item.model_dump(mode="json") for item in export.evidence_spans],
            "entities": [item.model_dump(mode="json") for item in export.entities],
            "claims": [item.model_dump(mode="json") for item in export.claims],
            "relationships": [item.model_dump(mode="json") for item in export.relationships],
            "evidence_links": [item.model_dump(mode="json") for item in export.evidence_links],
            "provenance": [item.model_dump(mode="json") for item in export.provenance],
            "unresolved_questions": [item.model_dump(mode="json") for item in export.unresolved_questions],
            "candidates": [item.model_dump(mode="json") for item in export.candidates],
            "actions": [item.model_dump(mode="json") for item in export.actions],
            "contradictions": [item.model_dump(mode="json") for item in export.contradictions],
            "origin_clusters": [item.model_dump(mode="json") for item in export.origin_clusters],
        },
        "policy_space": record_policy_space(export),
    }
    checkpoint = Checkpoint(
        id=new_id("cp"),
        investigation_id=export.investigation.id,
        step=step,
        state_json=state,
        stop_reason=recorded_stop,
        created_at=datetime.now(timezone.utc),
        summary=summary,
    )
    database.insert_checkpoint(checkpoint)
    from exploration.backend.trace import record_event

    payload = {
        "checkpoint_id": checkpoint.id,
        "step": step,
        "summary": summary,
        "stop_reason": recorded_stop,
        "unresolved": recorded_stop == "unresolved_uncertainty",
        "verified_success": False,
        "question": export.investigation.question,
        "open_questions": [question.text for question in export.unresolved_questions],
        "decision_source": export.investigation.decision_source,
        "decision_rationale": export.investigation.decision_rationale,
        "alternatives": [
            {
                "id": action.id,
                "query": action.query,
                "reason": action.reason,
                "utility": action.utility,
                "already_executed": action.already_executed,
            }
            for action in export.actions
        ],
        "parent_investigation_id": export.investigation.metadata.get("parent_investigation_id"),
        "intervention_type": export.investigation.metadata.get("intervention_type"),
        "from_checkpoint_id": export.investigation.metadata.get("branch_from_checkpoint_id"),
    }
    if extra:
        payload.update(extra)
    record_event(
        database,
        export.investigation.id,
        "checkpoint",
        payload,
        summary=summary,
        checkpoint_id=checkpoint.id,
    )
    return checkpoint


def list_checkpoints(database: Database, investigation_id: str) -> list[Checkpoint]:
    return database.list_checkpoints(investigation_id)
