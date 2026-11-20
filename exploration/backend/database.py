"""SQLite persistence for investigations, evidence, and checkpoints."""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

from shared.contracts import (
    BranchConstraints,
    BranchRecord,
    Checkpoint,
    Claim,
    Contradiction,
    ConvergenceDecision,
    Document,
    DocumentVersion,
    Entity,
    EvidenceCandidate,
    EvidenceLink,
    EvidenceSpan,
    ExplorationExport,
    GroundedAnswer,
    Investigation,
    InvestigationAction,
    KnowledgeAssertionIn,
    OriginCluster,
    Relationship,
    ResearchProfile,
    SourceProvenance,
    TraceEvent,
    UnresolvedQuestion,
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS investigations (
    id TEXT PRIMARY KEY,
    question TEXT NOT NULL,
    status TEXT NOT NULL,
    stop_reason TEXT,
    decision_source TEXT,
    decision_rationale TEXT,
    decision_json TEXT,
    session_id TEXT,
    budget_json TEXT NOT NULL,
    usage_json TEXT NOT NULL,
    metadata_json TEXT NOT NULL,
    live_extraction_blocked INTEGER NOT NULL,
    blocker TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS documents (
    investigation_id TEXT NOT NULL,
    id TEXT NOT NULL,
    canonical_url TEXT NOT NULL,
    title TEXT NOT NULL,
    origin_id TEXT,
    providers_json TEXT NOT NULL,
    PRIMARY KEY (investigation_id, id)
);
CREATE TABLE IF NOT EXISTS document_versions (
    id TEXT PRIMARY KEY,
    investigation_id TEXT NOT NULL,
    document_id TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    content TEXT NOT NULL,
    publish_date TEXT,
    UNIQUE (document_id, content_hash)
);
CREATE TABLE IF NOT EXISTS evidence_spans (
    investigation_id TEXT NOT NULL,
    id TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    PRIMARY KEY (investigation_id, id)
);
CREATE TABLE IF NOT EXISTS entities (
    investigation_id TEXT NOT NULL,
    id TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    PRIMARY KEY (investigation_id, id)
);
CREATE TABLE IF NOT EXISTS claims (
    investigation_id TEXT NOT NULL,
    id TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    PRIMARY KEY (investigation_id, id)
);
CREATE TABLE IF NOT EXISTS relationships (
    investigation_id TEXT NOT NULL,
    id TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    PRIMARY KEY (investigation_id, id)
);
CREATE TABLE IF NOT EXISTS evidence_links (
    investigation_id TEXT NOT NULL,
    id TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    PRIMARY KEY (investigation_id, id)
);
CREATE TABLE IF NOT EXISTS provenance (
    investigation_id TEXT NOT NULL,
    id TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    PRIMARY KEY (investigation_id, id)
);
CREATE TABLE IF NOT EXISTS unresolved_questions (
    investigation_id TEXT NOT NULL,
    id TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    PRIMARY KEY (investigation_id, id)
);
CREATE TABLE IF NOT EXISTS actions (
    investigation_id TEXT NOT NULL,
    id TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    PRIMARY KEY (investigation_id, id)
);
CREATE TABLE IF NOT EXISTS candidates (
    investigation_id TEXT NOT NULL,
    id TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    PRIMARY KEY (investigation_id, id)
);
CREATE TABLE IF NOT EXISTS contradictions (
    investigation_id TEXT NOT NULL,
    id TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    PRIMARY KEY (investigation_id, id)
);
CREATE TABLE IF NOT EXISTS origin_clusters (
    investigation_id TEXT NOT NULL,
    origin_id TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    PRIMARY KEY (investigation_id, origin_id)
);
CREATE TABLE IF NOT EXISTS checkpoints (
    id TEXT PRIMARY KEY,
    investigation_id TEXT NOT NULL,
    step INTEGER NOT NULL,
    state_json TEXT NOT NULL,
    stop_reason TEXT,
    created_at TEXT NOT NULL,
    summary TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS search_history (
    id TEXT PRIMARY KEY,
    investigation_id TEXT NOT NULL,
    query TEXT NOT NULL,
    session_id TEXT,
    interaction_id TEXT,
    providers_json TEXT NOT NULL,
    raw_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    network INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS investigation_events (
    id TEXT PRIMARY KEY,
    investigation_id TEXT NOT NULL,
    sequence INTEGER NOT NULL,
    stage TEXT NOT NULL,
    summary TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    checkpoint_id TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS branches (
    id TEXT PRIMARY KEY,
    parent_investigation_id TEXT NOT NULL,
    child_investigation_id TEXT NOT NULL,
    from_checkpoint_id TEXT NOT NULL,
    intervention_type TEXT NOT NULL,
    objective TEXT NOT NULL,
    constraints_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS idempotency_keys (
    key TEXT NOT NULL,
    route TEXT NOT NULL,
    request_hash TEXT NOT NULL,
    response_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (key, route)
);
CREATE TABLE IF NOT EXISTS knowledge_assertions (
    id TEXT PRIMARY KEY,
    profile_id TEXT NOT NULL,
    investigation_id TEXT,
    subject TEXT NOT NULL,
    predicate TEXT NOT NULL,
    object TEXT NOT NULL,
    text TEXT NOT NULL,
    epistemic_state TEXT NOT NULL,
    basis TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


def _dump(model) -> str:
    if hasattr(model, "model_dump"):
        return json.dumps(model.model_dump(mode="json"))
    return json.dumps(model)


def _load_model(cls, raw: str):
    return cls.model_validate(json.loads(raw))


class Database:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def insert_investigation(self, investigation: Investigation) -> None:
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO investigations (
                    id, question, status, stop_reason, decision_source, decision_rationale,
                    decision_json, session_id, budget_json, usage_json, metadata_json,
                    live_extraction_blocked, blocker, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    investigation.id,
                    investigation.question,
                    investigation.status,
                    investigation.stop_reason,
                    investigation.decision_source,
                    investigation.decision_rationale,
                    None,
                    investigation.session_id,
                    _dump(investigation.budget),
                    _dump(investigation.usage),
                    json.dumps(investigation.metadata),
                    int(investigation.live_extraction_blocked),
                    investigation.blocker,
                    investigation.created_at.isoformat(),
                    investigation.updated_at.isoformat(),
                ),
            )
            self._conn.commit()

    def update_investigation(self, investigation: Investigation, decision: ConvergenceDecision | None) -> None:
        """Persist status and budget. The original question column is never updated."""
        with self._lock:
            row = self._conn.execute(
                "SELECT question FROM investigations WHERE id = ?",
                (investigation.id,),
            ).fetchone()
            if row is None:
                raise KeyError(investigation.id)
            if row["question"] != investigation.question:
                raise ValueError("original research question is immutable")
            self._conn.execute(
                """
                UPDATE investigations SET
                    status = ?, stop_reason = ?, decision_source = ?, decision_rationale = ?,
                    decision_json = ?, session_id = ?, budget_json = ?, usage_json = ?,
                    metadata_json = ?, live_extraction_blocked = ?, blocker = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    investigation.status,
                    investigation.stop_reason,
                    investigation.decision_source,
                    investigation.decision_rationale,
                    _dump(decision) if decision is not None else None,
                    investigation.session_id,
                    _dump(investigation.budget),
                    _dump(investigation.usage),
                    json.dumps(investigation.metadata),
                    int(investigation.live_extraction_blocked),
                    investigation.blocker,
                    investigation.updated_at.isoformat(),
                    investigation.id,
                ),
            )
            self._conn.commit()

    def insert_version_if_absent(self, investigation_id: str, version: DocumentVersion) -> DocumentVersion:
        with self._lock:
            existing = self._conn.execute(
                "SELECT * FROM document_versions WHERE document_id = ? AND content_hash = ?",
                (version.document_id, version.content_hash),
            ).fetchone()
            if existing is not None:
                return _version_from_row(existing)
            by_id = self._conn.execute(
                "SELECT * FROM document_versions WHERE id = ?",
                (version.id,),
            ).fetchone()
            if by_id is not None:
                return _version_from_row(by_id)
            self._conn.execute(
                """
                INSERT INTO document_versions (
                    id, investigation_id, document_id, content_hash, fetched_at, content, publish_date
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    version.id,
                    investigation_id,
                    version.document_id,
                    version.content_hash,
                    version.fetched_at.isoformat(),
                    version.content,
                    version.publish_date,
                ),
            )
            self._conn.commit()
            return version

    def upsert_document(self, investigation_id: str, document: Document) -> None:
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO documents (investigation_id, id, canonical_url, title, origin_id, providers_json)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(investigation_id, id) DO UPDATE SET
                    canonical_url = excluded.canonical_url,
                    title = excluded.title,
                    origin_id = excluded.origin_id,
                    providers_json = excluded.providers_json
                """,
                (
                    investigation_id,
                    document.id,
                    document.canonical_url,
                    document.title,
                    document.origin_id,
                    json.dumps(document.providers),
                ),
            )
            self._conn.commit()

    def replace_graph_rows(self, export: ExplorationExport) -> None:
        investigation_id = export.investigation.id
        tables = [
            "evidence_spans",
            "entities",
            "claims",
            "relationships",
            "evidence_links",
            "provenance",
            "unresolved_questions",
            "actions",
            "candidates",
            "contradictions",
            "origin_clusters",
        ]
        with self._lock:
            for table in tables:
                self._conn.execute(f"DELETE FROM {table} WHERE investigation_id = ?", (investigation_id,))
            self._insert_payloads(investigation_id, "evidence_spans", export.evidence_spans)
            self._insert_payloads(investigation_id, "entities", export.entities)
            self._insert_payloads(investigation_id, "claims", export.claims)
            self._insert_payloads(investigation_id, "relationships", export.relationships)
            self._insert_payloads(investigation_id, "evidence_links", export.evidence_links)
            self._insert_payloads(investigation_id, "provenance", export.provenance)
            self._insert_payloads(investigation_id, "unresolved_questions", export.unresolved_questions)
            self._insert_payloads(investigation_id, "actions", export.actions)
            self._insert_payloads(investigation_id, "candidates", export.candidates)
            self._insert_payloads(investigation_id, "contradictions", export.contradictions)
            for cluster in export.origin_clusters:
                self._conn.execute(
                    "INSERT INTO origin_clusters (investigation_id, origin_id, payload_json) VALUES (?, ?, ?)",
                    (investigation_id, cluster.origin_id, _dump(cluster)),
                )
            self._conn.commit()

    def _insert_payloads(self, investigation_id: str, table: str, models) -> None:
        seen: set[str] = set()
        for model in models:
            if model.id in seen:
                continue
            seen.add(model.id)
            self._conn.execute(
                f"INSERT INTO {table} (investigation_id, id, payload_json) VALUES (?, ?, ?)",
                (investigation_id, model.id, _dump(model)),
            )

    def insert_checkpoint(self, checkpoint: Checkpoint) -> None:
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO checkpoints (id, investigation_id, step, state_json, stop_reason, created_at, summary)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    checkpoint.id,
                    checkpoint.investigation_id,
                    checkpoint.step,
                    json.dumps(checkpoint.state_json),
                    checkpoint.stop_reason,
                    checkpoint.created_at.isoformat(),
                    checkpoint.summary,
                ),
            )
            self._conn.commit()

    def list_checkpoints(self, investigation_id: str) -> list[Checkpoint]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM checkpoints WHERE investigation_id = ? ORDER BY step ASC, created_at ASC",
                (investigation_id,),
            ).fetchall()
        return [
            Checkpoint(
                id=row["id"],
                investigation_id=row["investigation_id"],
                step=row["step"],
                state_json=json.loads(row["state_json"]),
                stop_reason=row["stop_reason"],
                created_at=datetime.fromisoformat(row["created_at"]),
                summary=row["summary"],
            )
            for row in rows
        ]

    def insert_search(
        self,
        *,
        search_id: str,
        investigation_id: str,
        query: str,
        session_id: str | None,
        interaction_id: str | None,
        providers: list[str],
        raw: dict[str, Any],
        created_at: datetime,
        network: bool,
    ) -> None:
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO search_history (
                    id, investigation_id, query, session_id, interaction_id, providers_json, raw_json, created_at, network
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    search_id,
                    investigation_id,
                    query,
                    session_id,
                    interaction_id,
                    json.dumps(providers),
                    json.dumps(raw),
                    created_at.isoformat(),
                    int(network),
                ),
            )
            self._conn.commit()

    def search_queries(self, investigation_id: str) -> list[str]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT query FROM search_history WHERE investigation_id = ? ORDER BY created_at ASC",
                (investigation_id,),
            ).fetchall()
        return [row["query"] for row in rows]

    def insert_event(
        self,
        *,
        event_id: str,
        investigation_id: str,
        stage: str,
        summary: str,
        payload: dict[str, Any],
        created_at: datetime,
        checkpoint_id: str | None = None,
    ) -> int:
        with self._lock:
            row = self._conn.execute(
                "SELECT COALESCE(MAX(sequence), 0) + 1 AS seq FROM investigation_events WHERE investigation_id = ?",
                (investigation_id,),
            ).fetchone()
            sequence = int(row["seq"])
            self._conn.execute(
                """
                INSERT INTO investigation_events (
                    id, investigation_id, sequence, stage, summary, payload_json, checkpoint_id, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    investigation_id,
                    sequence,
                    stage,
                    summary,
                    json.dumps(payload),
                    checkpoint_id,
                    created_at.isoformat(),
                ),
            )
            self._conn.commit()
            return sequence

    def list_events(self, investigation_id: str) -> list[TraceEvent]:
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT * FROM investigation_events
                WHERE investigation_id = ?
                ORDER BY sequence ASC, created_at ASC
                """,
                (investigation_id,),
            ).fetchall()
        return [
            TraceEvent(
                id=row["id"],
                investigation_id=row["investigation_id"],
                sequence=row["sequence"],
                stage=row["stage"],
                summary=row["summary"],
                payload=json.loads(row["payload_json"]),
                checkpoint_id=row["checkpoint_id"],
                created_at=datetime.fromisoformat(row["created_at"]),
            )
            for row in rows
        ]

    def insert_branch(self, branch: BranchRecord) -> None:
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO branches (
                    id, parent_investigation_id, child_investigation_id, from_checkpoint_id,
                    intervention_type, objective, constraints_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    branch.id,
                    branch.parent_investigation_id,
                    branch.child_investigation_id,
                    branch.from_checkpoint_id,
                    branch.intervention_type,
                    branch.objective,
                    _dump(branch.constraints),
                    branch.created_at.isoformat(),
                ),
            )
            self._conn.commit()

    def get_branch(self, branch_id: str) -> BranchRecord | None:
        with self._lock:
            row = self._conn.execute("SELECT * FROM branches WHERE id = ?", (branch_id,)).fetchone()
        if row is None:
            return None
        return _branch_from_row(row)

    def list_branches(self, investigation_id: str) -> list[BranchRecord]:
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT * FROM branches
                WHERE parent_investigation_id = ? OR child_investigation_id = ?
                ORDER BY created_at ASC
                """,
                (investigation_id, investigation_id),
            ).fetchall()
        return [_branch_from_row(row) for row in rows]

    def insert_assertion(self, assertion_id: str, body: KnowledgeAssertionIn, created_at: datetime) -> None:
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO knowledge_assertions (
                    id, profile_id, investigation_id, subject, predicate, object, text,
                    epistemic_state, basis, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    assertion_id,
                    body.profile_id,
                    body.investigation_id,
                    body.subject,
                    body.predicate,
                    body.object,
                    body.text,
                    body.epistemic_state,
                    body.basis,
                    created_at.isoformat(),
                ),
            )
            self._conn.commit()

    def list_assertions(self, profile_id: str) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM knowledge_assertions WHERE profile_id = ? ORDER BY created_at ASC",
                (profile_id,),
            ).fetchall()
        return [
            {
                "id": row["id"],
                "profile_id": row["profile_id"],
                "investigation_id": row["investigation_id"],
                "subject": row["subject"],
                "predicate": row["predicate"],
                "object": row["object"],
                "text": row["text"],
                "epistemic_state": row["epistemic_state"],
                "basis": row["basis"],
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    def list_investigations(self, limit: int = 50, offset: int = 0) -> tuple[list[dict[str, Any]], int]:
        """Newest first. Read-only summary rows for the investigation picker."""
        with self._lock:
            total = self._conn.execute("SELECT COUNT(*) FROM investigations").fetchone()[0]
            rows = self._conn.execute(
                """
                SELECT i.id, i.question, i.status, i.stop_reason, i.created_at, i.updated_at, i.metadata_json, i.usage_json,
                       (SELECT COUNT(*) FROM investigation_events e WHERE e.investigation_id = i.id) AS event_count,
                       (SELECT COUNT(*) FROM checkpoints c WHERE c.investigation_id = i.id) AS checkpoint_count,
                       b.id AS branch_id, b.parent_investigation_id AS branch_parent,
                       b.intervention_type AS branch_intervention, b.from_checkpoint_id AS branch_checkpoint
                FROM investigations i
                LEFT JOIN branches b ON b.child_investigation_id = i.id
                ORDER BY i.created_at DESC, i.id
                LIMIT ? OFFSET ?
                """,
                (limit, offset),
            ).fetchall()
        items: list[dict[str, Any]] = []
        for row in rows:
            try:
                metadata = json.loads(row["metadata_json"] or "{}")
            except ValueError:
                metadata = {}
            items.append(
                {
                    "id": row["id"],
                    "question": row["question"],
                    "status": row["status"],
                    "stop_reason": row["stop_reason"],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                    "parent_investigation_id": metadata.get("parent_investigation_id") or row["branch_parent"],
                    "branch_id": metadata.get("branch_id") or row["branch_id"],
                    "intervention_type": metadata.get("intervention_type") or row["branch_intervention"],
                    "from_checkpoint_id": metadata.get("branch_from_checkpoint_id") or row["branch_checkpoint"],
                    "event_count": row["event_count"],
                    "checkpoint_count": row["checkpoint_count"],
                    "root_question": metadata.get("root_question") or self._lineage_root_question(metadata),
                    "lifecycle": _row_lifecycle(row, metadata),
                }
            )
        return items, total

    def get_idempotent(self, key: str, route: str) -> tuple[str, str] | None:
        """(request_hash, response_json) previously stored for this key and route."""
        with self._lock:
            row = self._conn.execute(
                "SELECT request_hash, response_json FROM idempotency_keys WHERE key = ? AND route = ?", (key, route)
            ).fetchone()
        return (row["request_hash"], row["response_json"]) if row else None

    def put_idempotent(self, key: str, route: str, request_hash: str, response_json: str, created_at: str) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT OR IGNORE INTO idempotency_keys (key, route, request_hash, response_json, created_at) VALUES (?, ?, ?, ?, ?)",
                (key, route, request_hash, response_json, created_at),
            )
            self._conn.commit()

    def _lineage_root_question(self, metadata: dict[str, Any]) -> str | None:
        """Root question for a legacy branch row (pre-1.1.0 rows overwrote their question)."""
        parent_id = metadata.get("parent_investigation_id")
        if not parent_id:
            return None
        question = None
        for _ in range(64):
            with self._lock:
                row = self._conn.execute(
                    "SELECT question, metadata_json FROM investigations WHERE id = ?", (parent_id,)
                ).fetchone()
            if row is None:
                return question
            question = row["question"]
            try:
                parent_meta = json.loads(row["metadata_json"] or "{}")
            except ValueError:
                parent_meta = {}
            if parent_meta.get("root_question"):
                return parent_meta["root_question"]
            parent_id = parent_meta.get("parent_investigation_id")
            if not parent_id:
                return question
        return question

    def load_export(self, investigation_id: str) -> ExplorationExport:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM investigations WHERE id = ?",
                (investigation_id,),
            ).fetchone()
            if row is None:
                raise KeyError(investigation_id)
            documents = [
                Document(
                    id=item["id"],
                    canonical_url=item["canonical_url"],
                    title=item["title"],
                    origin_id=item["origin_id"],
                    providers=json.loads(item["providers_json"]),
                )
                for item in self._conn.execute(
                    "SELECT * FROM documents WHERE investigation_id = ?",
                    (investigation_id,),
                ).fetchall()
            ]
            versions = [
                _version_from_row(item)
                for item in self._conn.execute(
                    "SELECT * FROM document_versions WHERE investigation_id = ?",
                    (investigation_id,),
                ).fetchall()
            ]
            decision = _load_model(ConvergenceDecision, row["decision_json"]) if row["decision_json"] else None
            metadata = json.loads(row["metadata_json"])
            profile_raw = metadata.get("profile_snapshot")
            profile = ResearchProfile.model_validate(profile_raw) if profile_raw else None
            checkpoints = [
                Checkpoint(
                    id=item["id"],
                    investigation_id=item["investigation_id"],
                    step=item["step"],
                    state_json=json.loads(item["state_json"]),
                    stop_reason=item["stop_reason"],
                    created_at=datetime.fromisoformat(item["created_at"]),
                    summary=item["summary"],
                )
                for item in self._conn.execute(
                    "SELECT * FROM checkpoints WHERE investigation_id = ? ORDER BY step ASC",
                    (investigation_id,),
                ).fetchall()
            ]
            export = ExplorationExport(
                investigation=Investigation(
                    id=row["id"],
                    question=row["question"],
                    budget=json.loads(row["budget_json"]),
                    status=row["status"],
                    stop_reason=row["stop_reason"],
                    decision_source=row["decision_source"],
                    decision_rationale=row["decision_rationale"],
                    session_id=row["session_id"],
                    usage=json.loads(row["usage_json"]),
                    created_at=datetime.fromisoformat(row["created_at"]),
                    updated_at=datetime.fromisoformat(row["updated_at"]),
                    live_extraction_blocked=bool(row["live_extraction_blocked"]),
                    blocker=row["blocker"],
                    metadata=metadata,
                ),
                documents=documents,
                document_versions=versions,
                evidence_spans=self._payloads(investigation_id, "evidence_spans", EvidenceSpan),
                entities=self._payloads(investigation_id, "entities", Entity),
                claims=self._payloads(investigation_id, "claims", Claim),
                relationships=self._payloads(investigation_id, "relationships", Relationship),
                evidence_links=self._payloads(investigation_id, "evidence_links", EvidenceLink),
                provenance=self._payloads(investigation_id, "provenance", SourceProvenance),
                unresolved_questions=self._payloads(investigation_id, "unresolved_questions", UnresolvedQuestion),
                actions=self._payloads(investigation_id, "actions", InvestigationAction),
                candidates=self._payloads(investigation_id, "candidates", EvidenceCandidate),
                contradictions=self._payloads(investigation_id, "contradictions", Contradiction),
                origin_clusters=[
                    OriginCluster.model_validate(json.loads(item["payload_json"]))
                    for item in self._conn.execute(
                        "SELECT payload_json FROM origin_clusters WHERE investigation_id = ?",
                        (investigation_id,),
                    ).fetchall()
                ],
                checkpoints=checkpoints,
                decision=decision,
                answer=(GroundedAnswer.model_validate(metadata["answer"]) if metadata.get("answer") else None),
                profile=profile,
            )
        return export

    def _payloads(self, investigation_id: str, table: str, cls):
        rows = self._conn.execute(
            f"SELECT payload_json FROM {table} WHERE investigation_id = ?",
            (investigation_id,),
        ).fetchall()
        return [_load_model(cls, row["payload_json"]) for row in rows]


def _branch_from_row(row: sqlite3.Row) -> BranchRecord:
    raw = json.loads(row["constraints_json"]) if row["constraints_json"] else {}
    return BranchRecord(
        id=row["id"],
        parent_investigation_id=row["parent_investigation_id"],
        child_investigation_id=row["child_investigation_id"],
        from_checkpoint_id=row["from_checkpoint_id"],
        intervention_type=row["intervention_type"],
        objective=row["objective"],
        created_at=datetime.fromisoformat(row["created_at"]),
        constraints=BranchConstraints.model_validate(raw),
    )


def _version_from_row(row: sqlite3.Row) -> DocumentVersion:
    return DocumentVersion(
        id=row["id"],
        document_id=row["document_id"],
        content_hash=row["content_hash"],
        fetched_at=datetime.fromisoformat(row["fetched_at"]),
        content=row["content"],
        publish_date=row["publish_date"],
    )


def _row_lifecycle(row, metadata: dict[str, Any]) -> str:
    """Same rule as trace.lifecycle_of, from a listing row (no full export load)."""
    try:
        usage = json.loads(row["usage_json"] or "{}")
    except ValueError:
        usage = {}
    explicit = metadata.get("lifecycle")
    status = row["status"]
    if explicit in {"failed", "queued"} and status != "stopped":
        return explicit
    is_branch = bool(metadata.get("branch_id") or metadata.get("parent_investigation_id") or row["branch_id"])
    if status == "blocked":
        return "failed"
    if status == "stopped":
        return "completed" if row["stop_reason"] == "evidence_sufficient" else "stopped"
    if status == "created":
        return "saved"
    if int(usage.get("search_calls") or 0) == 0 and is_branch:
        return "saved"
    return "researching"
