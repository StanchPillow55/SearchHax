"""SQLite persistence for investigations, evidence, and checkpoints."""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

from shared.contracts import (
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
    Investigation,
    InvestigationAction,
    OriginCluster,
    Relationship,
    ResearchProfile,
    SourceProvenance,
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
                profile=profile,
            )
        return export

    def _payloads(self, investigation_id: str, table: str, cls):
        rows = self._conn.execute(
            f"SELECT payload_json FROM {table} WHERE investigation_id = ?",
            (investigation_id,),
        ).fetchall()
        return [_load_model(cls, row["payload_json"]) for row in rows]


def _version_from_row(row: sqlite3.Row) -> DocumentVersion:
    return DocumentVersion(
        id=row["id"],
        document_id=row["document_id"],
        content_hash=row["content_hash"],
        fetched_at=datetime.fromisoformat(row["fetched_at"]),
        content=row["content"],
        publish_date=row["publish_date"],
    )
