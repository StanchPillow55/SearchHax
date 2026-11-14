"""Evidence graph operations over the SQLite store.

Document versions are immutable. Equivalent documents are deduplicated by
canonical URL inside one investigation, while every provider that found the
URL stays on the document.
"""

from __future__ import annotations

from shared.contracts import Document, DocumentVersion, ExplorationExport, Investigation

from exploration.backend.database import Database
from exploration.backend.ids import stable_id


class EvidenceGraph:
    def __init__(self, database: Database):
        self.database = database

    def load(self, investigation_id: str) -> ExplorationExport:
        return self.database.load_export(investigation_id)

    def save(self, export: ExplorationExport) -> None:
        stored = self.database.load_export(export.investigation.id)
        if stored.investigation.question != export.investigation.question:
            raise ValueError("original research question is immutable")
        for version in export.document_versions:
            self.database.insert_version_if_absent(export.investigation.id, version)
        for document in export.documents:
            self.database.upsert_document(export.investigation.id, document)
        self.database.replace_graph_rows(export)
        self.database.update_investigation(export.investigation, export.decision)

    def ensure_document(
        self,
        investigation: Investigation,
        *,
        canonical_url: str,
        title: str,
        providers: list[str],
        content: str,
        content_hash: str,
        fetched_at,
        publish_date: str | None,
        origin_id: str | None = None,
    ) -> tuple[Document, DocumentVersion, bool]:
        """Return the document, the stored version, and whether this content is new."""
        document_id = stable_id("doc", investigation.id, canonical_url)
        version_id = stable_id("ver", document_id, content_hash)
        document = Document(
            id=document_id,
            canonical_url=canonical_url,
            title=title,
            origin_id=origin_id,
            providers=list(dict.fromkeys(providers)),
        )
        version = DocumentVersion(
            id=version_id,
            document_id=document_id,
            content_hash=content_hash,
            fetched_at=fetched_at,
            content=content,
            publish_date=publish_date,
        )
        self.database.upsert_document(investigation.id, document)
        stored = self.database.insert_version_if_absent(investigation.id, version)
        created = stored.id == version.id and stored.content_hash == content_hash and stored.content == content
        # insert_version_if_absent returns the existing row when the hash is already stored.
        # created is true only when the row we just built was the one persisted with this content.
        existed = stored.content == content and stored.content_hash == content_hash and stored.id != version.id
        return document, stored, not existed and stored.content == content
