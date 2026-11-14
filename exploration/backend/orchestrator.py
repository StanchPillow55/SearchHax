"""Bounded investigation loop.

The backend asks the convergence controller which follow-up to run, then clamps
the answer to the hard search and fetch caps. If the controller is down, the
labeled fallback runs at most one non-duplicate query. This module does not
implement intent alignment, novelty, or redundancy policy.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

from shared.contracts import (
    Document,
    DocumentVersion,
    EvidenceCandidate,
    ExplorationExport,
    Investigation,
    InvestigationBudget,
    SourceProvenance,
    UnresolvedQuestion,
)

from exploration.backend.attention import score_passage
from exploration.backend.budget import BudgetExceededError, BudgetGuard, clamp_budget
from exploration.backend.checkpoints import save_checkpoint
from exploration.backend.config import default_db_path, llm_api_key, telem_configured
from exploration.backend.convergence import build_request, evaluate_controller
from exploration.backend.database import Database
from exploration.backend.extraction import ExtractionBatch, extract_document, merge_batches
from exploration.backend.llm import OpenAICompatibleClient
from exploration.backend.graph import EvidenceGraph
from exploration.backend.ids import content_hash, new_id, stable_id
from exploration.backend.planner import generate_actions, initial_search_query
from exploration.backend.retrieval import RetrievalClient, normalize_url
from exploration.backend.story_c import STORY_C_QUESTION, load_story_c
from exploration.backend.verification import classify_provenance, origin_clusters, reconcile_amount_conflicts

STORY_A_QUESTION = (
    "How do NVIDIA's investments, GPU infrastructure customers, and AI capacity expansion reinforce one another?"
)
INDEPENDENCE_QUESTION = (
    "independent primary confirmation of the Lumenarc Dynamics Series D amount "
    "that does not cite wire LF-PR-2026-031"
)


class Orchestrator:
    def __init__(self, db_path: str | Path | None = None, retrieval: RetrievalClient | None = None, post=None, convergence_url: str | None = None):
        self.database = Database(db_path or default_db_path())
        self.graph = EvidenceGraph(self.database)
        self.retrieval = retrieval or RetrievalClient()
        self.post = post
        self.convergence_url = convergence_url

    def create(self, question: str, budget: InvestigationBudget | None = None, *, mode: str = "web") -> Investigation:
        now = _now()
        investigation = Investigation(
            id=new_id("inv"),
            question=question.strip(),
            budget=clamp_budget(budget),
            status="created",
            usage={"configuration": mode},
            created_at=now,
            updated_at=now,
            metadata={"mode": mode},
        )
        self.database.insert_investigation(investigation)
        return investigation

    def get(self, investigation_id: str) -> ExplorationExport:
        return self.graph.load(investigation_id)

    def resume(self, investigation_id: str) -> dict[str, int]:
        """Reload stored evidence. Unchanged cached or stored text is not fetched again."""
        export = self.graph.load(investigation_id)
        stats = {"reused": 0, "unchanged_versions": 0, "network_fetches": 0}
        documents = {document.id: document for document in export.documents}
        for version in export.document_versions:
            document = documents.get(version.document_id)
            if document is None:
                continue
            cached = self.retrieval.cached_fetch(document.canonical_url)
            if cached and cached.content_hash == version.content_hash and cached.content == version.content:
                stats["reused"] += 1
                continue
            if version.content_hash == content_hash(version.content):
                stats["unchanged_versions"] += 1
                continue
            stats["network_fetches"] += 1
            if not self.retrieval.dry_run:
                self.retrieval.fetch([document.canonical_url], session_id=export.investigation.session_id)
        return stats

    def run_story_c(
        self,
        *,
        reconcile: bool = True,
        follow_up: bool = True,
        classify: bool = True,
        configuration: str = "B3",
    ) -> ExplorationExport:
        started = _now_seconds()
        investigation = self.create(STORY_C_QUESTION, mode="story_c")
        investigation.usage.configuration = configuration
        batches: list[ExtractionBatch] = []
        documents: list[Document] = []
        versions: list[DocumentVersion] = []
        provenance: list[SourceProvenance] = []
        for fixture in load_story_c():
            canonical = normalize_url(fixture.url)
            digest = content_hash(fixture.content)
            document = Document(
                id=stable_id("doc", investigation.id, canonical),
                canonical_url=canonical,
                title=fixture.title,
                providers=["fixture"],
            )
            version = DocumentVersion(
                id=stable_id("ver", document.id, digest),
                document_id=document.id,
                content_hash=digest,
                fetched_at=_now(),
                content=fixture.content,
                publish_date=fixture.publish_date,
            )
            batch = extract_document(
                fixture.content,
                url=canonical,
                document_id=document.id,
                version_id=version.id,
                version_hash=digest,
                question=investigation.question,
                explicit_fixture=True,
                publish_date=fixture.publish_date,
            )
            batches.append(batch)
            if classify:
                item = classify_provenance(document.id, canonical, fixture.content, ["fixture"])
                document.origin_id = item.origin_id
            else:
                item = SourceProvenance(
                    id=stable_id("prov", document.id, "b0"),
                    document_id=document.id,
                    provider="fixture",
                    providers=["fixture"],
                    origin_kind="unknown",
                    notes="B0 stores the document without cross-document provenance classification.",
                )
            documents.append(document)
            versions.append(version)
            provenance.append(item)

        merged = merge_batches(batches)
        contradictions = []
        if classify and reconcile:
            contradictions = reconcile_amount_conflicts(merged.relationships, merged.claims, merged.links, provenance)
        clusters = origin_clusters(provenance) if classify else []
        questions: list[UnresolvedQuestion] = []
        if classify and any(cluster.derivative_document_ids for cluster in clusters):
            questions.append(
                UnresolvedQuestion(
                    id=stable_id("q", investigation.id, "independence"),
                    text=INDEPENDENCE_QUESTION,
                    importance=0.9,
                    missing_evidence=1.0,
                    kind="independence",
                )
            )
        candidates = [
            _candidate(investigation.question, document, version, questions)
            for document, version in zip(documents, versions, strict=True)
        ]
        actions = generate_actions(questions, []) if follow_up else []
        investigation.status = "running"
        investigation.live_extraction_blocked = merged.live_extraction_blocked
        investigation.blocker = merged.blocker
        investigation.usage.corpus_documents = len(documents)
        investigation.usage.rejected_ungrounded_citations = merged.rejected_ungrounded
        investigation.usage.providers_used = ["fixture"]
        investigation.updated_at = _now()
        export = ExplorationExport(
            investigation=investigation,
            documents=documents,
            document_versions=versions,
            evidence_spans=merged.spans,
            entities=merged.entities,
            claims=merged.claims,
            relationships=merged.relationships,
            evidence_links=merged.links,
            provenance=provenance,
            unresolved_questions=questions,
            candidates=candidates,
            actions=actions,
            contradictions=contradictions,
            origin_clusters=clusters,
        )
        self._persist(export)
        save_checkpoint(self.database, export, step=1, summary="Ingested the Story C fixture corpus with no network calls.")
        if not follow_up:
            investigation.status = "stopped"
            investigation.usage.latency_ms = _elapsed_ms(started)
            investigation.updated_at = _now()
            self._persist(export)
            save_checkpoint(self.database, export, step=2, summary="B0 single pass stopped without a follow-up or provenance graph.")
            return self.graph.load(investigation.id)

        decision = evaluate_controller(
            build_request(
                investigation_id=investigation.id,
                question=investigation.question,
                questions=questions,
                candidates=candidates,
                actions=actions,
                budget=investigation.budget,
                usage=investigation.usage,
            ),
            followups_executed=investigation.usage.followups_executed,
            url=self.convergence_url,
            post=self.post,
        )
        export.decision = decision
        investigation.decision_source = decision.decision_source
        investigation.decision_rationale = decision.rationale
        if decision.approved_action and not decision.stop:
            try:
                self._local_follow_up(export, decision)
            except BudgetExceededError:
                investigation.stop_reason = "budget_exhausted"
                decision.stop = True
                decision.stop_reason = "budget_exhausted"
        if investigation.stop_reason is None:
            if decision.stop and decision.stop_reason:
                investigation.stop_reason = decision.stop_reason
            elif questions and any(question.missing_evidence >= 0.5 for question in questions):
                investigation.stop_reason = "unresolved_uncertainty"
            elif not actions and not questions:
                investigation.stop_reason = "evidence_sufficient"
            else:
                investigation.stop_reason = decision.stop_reason or "no_useful_actions"
        investigation.status = "stopped"
        investigation.usage.latency_ms = _elapsed_ms(started)
        investigation.updated_at = _now()
        self._persist(export)
        save_checkpoint(
            self.database,
            export,
            step=2,
            summary="Recorded the controller or fallback decision and any one local follow-up.",
            stop_reason=investigation.stop_reason,
        )
        return self.graph.load(investigation.id)

    def step(self, investigation_id: str) -> ExplorationExport:
        export = self.graph.load(investigation_id)
        investigation = export.investigation
        if investigation.status in {"stopped", "blocked"}:
            return export
        if investigation.metadata.get("mode") == "story_c":
            return export
        if not export.documents and investigation.usage.search_calls == 0:
            return self._initial_web_step(export)
        return self._follow_up_web_step(export)

    def _initial_web_step(self, export: ExplorationExport) -> ExplorationExport:
        investigation = export.investigation
        if not telem_configured() and not self.retrieval.dry_run:
            investigation.status = "blocked"
            investigation.blocker = "TELEM_API_KEY missing"
            investigation.live_extraction_blocked = llm_api_key() is None
            investigation.updated_at = _now()
            self._persist(export)
            save_checkpoint(self.database, export, step=1, summary="Blocked before search: TELEM_API_KEY missing. No results were invented.")
            return self.graph.load(investigation.id)
        started = _now_seconds()
        guard = BudgetGuard(investigation.budget)
        try:
            bundle = self.retrieval.search(
                initial_search_query(investigation.question),
                session_id=investigation.session_id,
                guard=guard,
            )
        except BudgetExceededError:
            return self._stop_budget(export, guard)
        investigation.budget = guard.budget
        self._record_search(investigation, bundle, network=not bundle.dry_run)
        self._ingest_bundle(export, bundle, guard)
        investigation.status = "running"
        investigation.updated_at = _now()
        self._persist(export)
        save_checkpoint(self.database, export, step=1, summary="Initial Telem search and shortlisted fetch.")
        investigation.usage.latency_ms = _elapsed_ms(started)
        if investigation.live_extraction_blocked and not export.relationships:
            investigation.status = "stopped"
            investigation.stop_reason = "unresolved_uncertainty"
            investigation.decision_source = "fallback"
            investigation.decision_rationale = (
                investigation.blocker
                or "Extraction produced no grounded relationships. Fallback did not invent any or spend a follow-up search."
            )
            investigation.updated_at = _now()
            self._persist(export)
            save_checkpoint(self.database, export, step=2, summary="Stopped without a follow-up because extraction is blocked.", stop_reason="unresolved_uncertainty")
        else:
            self._persist(export)
        return self.graph.load(investigation.id)

    def _follow_up_web_step(self, export: ExplorationExport) -> ExplorationExport:
        investigation = export.investigation
        actions = generate_actions(export.unresolved_questions, self.database.search_queries(investigation.id))
        export.actions = actions
        decision = evaluate_controller(
            build_request(
                investigation_id=investigation.id,
                question=investigation.question,
                questions=export.unresolved_questions,
                candidates=export.candidates,
                actions=actions,
                budget=investigation.budget,
                usage=investigation.usage,
            ),
            followups_executed=investigation.usage.followups_executed,
            url=self.convergence_url,
            post=self.post,
        )
        export.decision = decision
        investigation.decision_source = decision.decision_source
        investigation.decision_rationale = decision.rationale
        guard = BudgetGuard(investigation.budget)
        already_searched = {query.strip().lower() for query in self.database.search_queries(investigation.id)}
        action = decision.approved_action
        duplicate_query = bool(action and action.query.strip().lower() in already_searched)
        if duplicate_query and action is not None:
            action.already_executed = True
            action.result_summary = "Skipped a query that was already searched."
        if action and not decision.stop and not duplicate_query:
            try:
                bundle = self.retrieval.search(
                    action.query,
                    session_id=investigation.session_id,
                    guard=guard,
                )
            except BudgetExceededError:
                return self._stop_budget(export, guard)
            investigation.budget = guard.budget
            self._record_search(investigation, bundle, network=not bundle.dry_run)
            self._ingest_bundle(export, bundle, guard)
            investigation.usage.followups_executed += 1
            decision.approved_action.already_executed = True
            decision.approved_action.result_summary = f"Follow-up returned {len(bundle.documents)} deduplicated URLs."
        if decision.stop and decision.stop_reason:
            investigation.stop_reason = decision.stop_reason
            investigation.status = "stopped"
        elif decision.decision_source == "fallback":
            investigation.stop_reason = (
                "unresolved_uncertainty" if export.unresolved_questions else "evidence_sufficient"
            )
            investigation.status = "stopped"
        elif investigation.budget.remaining_searches <= 0:
            investigation.stop_reason = "budget_exhausted"
            investigation.status = "stopped"
        else:
            investigation.status = "running"
        investigation.updated_at = _now()
        self._persist(export)
        save_checkpoint(self.database, export, step=2, summary="Follow-up decision applied within the backend budget.", stop_reason=investigation.stop_reason)
        return self.graph.load(investigation.id)

    def _local_follow_up(self, export: ExplorationExport, decision) -> None:
        investigation = export.investigation
        guard = BudgetGuard(investigation.budget)
        guard.authorize_search()
        investigation.budget = guard.budget
        action = decision.approved_action
        independent: list[str] = []
        for version in export.document_versions:
            has_amount = re.search(r"\$\d+ million Series D", version.content) is not None
            cites_wire = "LF-PR-2026-031" in version.content
            if has_amount and not cites_wire:
                independent.append(version.document_id)
        summary = (
            "No document in the local corpus states a Series D amount without citing wire LF-PR-2026-031."
            if not independent
            else "Found local documents that state an amount without the wire id: " + ", ".join(independent)
        )
        action.already_executed = True
        action.result_summary = summary
        for existing in export.actions:
            if existing.id == action.id:
                existing.already_executed = True
                existing.result_summary = summary
        investigation.usage.search_calls += 1
        investigation.usage.followups_executed += 1
        self.database.insert_search(
            search_id=new_id("search"),
            investigation_id=investigation.id,
            query=action.query,
            session_id=None,
            interaction_id=None,
            providers=["local_corpus"],
            raw={"independent_document_ids": independent, "network": False},
            created_at=_now(),
            network=False,
        )

    def _record_search(self, investigation: Investigation, bundle, *, network: bool) -> None:
        investigation.usage.search_calls += 1
        investigation.usage.provider_calls += bundle.provider_call_count
        if network:
            investigation.usage.network_calls += 1
        if bundle.session_id:
            investigation.session_id = bundle.session_id
            investigation.usage.session_id = bundle.session_id
        if bundle.interaction_id and bundle.interaction_id not in investigation.usage.interaction_ids:
            investigation.usage.interaction_ids.append(bundle.interaction_id)
        for provider in [hit.provider for document in bundle.documents for hit in document.hits]:
            if provider not in investigation.usage.providers_used:
                investigation.usage.providers_used.append(provider)
        self.database.insert_search(
            search_id=new_id("search"),
            investigation_id=investigation.id,
            query=bundle.query,
            session_id=bundle.session_id,
            interaction_id=bundle.interaction_id,
            providers=sorted({hit.provider for hit in bundle.provider_hits}),
            raw=bundle.raw,
            created_at=_now(),
            network=network,
        )

    def _ingest_bundle(self, export: ExplorationExport, bundle, guard: BudgetGuard) -> None:
        investigation = export.investigation
        ranked = []
        for document in bundle.documents:
            gaps = [question.text for question in export.unresolved_questions]
            attention = score_passage(investigation.question, document.snippet or document.title, gaps, document.publish_date)
            ranked.append((attention.score, document, attention))
        ranked.sort(key=lambda item: item[0], reverse=True)
        chosen = [item for item in ranked if item[1].canonical_url not in {doc.canonical_url for doc in export.documents}]
        chosen = chosen[: min(5, investigation.budget.remaining_fetched_urls)]
        pages = []
        if chosen:
            fetched_before = investigation.budget.urls_fetched
            pages = self.retrieval.fetch(
                [item[1].canonical_url for item in chosen],
                session_id=investigation.session_id,
                guard=guard,
            )
            investigation.budget = guard.budget
            investigation.usage.fetch_calls += 1
            investigation.usage.urls_fetched = investigation.budget.urls_fetched
            if investigation.budget.urls_fetched > fetched_before:
                investigation.usage.network_calls += 1
        page_by_url = {page.canonical_url: page for page in pages}
        batches: list[ExtractionBatch] = []
        for _score, merged, attention in chosen:
            page = page_by_url.get(merged.canonical_url)
            content = page.content if page else ""
            if not content:
                continue
            digest = content_hash(content)
            document = Document(
                id=stable_id("doc", investigation.id, merged.canonical_url),
                canonical_url=merged.canonical_url,
                title=merged.title or (page.title if page else ""),
                providers=list(merged.providers),
            )
            version = DocumentVersion(
                id=stable_id("ver", document.id, digest),
                document_id=document.id,
                content_hash=digest,
                fetched_at=_now(),
                content=content,
                publish_date=merged.publish_date,
            )
            export.documents.append(document)
            export.document_versions.append(version)
            export.provenance.append(
                classify_provenance(document.id, merged.canonical_url, content, list(merged.providers))
                if is_fixture_url(merged.canonical_url)
                else SourceProvenance(
                    id=stable_id("prov", document.id, merged.canonical_url),
                    document_id=document.id,
                    provider=merged.providers[0] if merged.providers else None,
                    providers=list(merged.providers),
                    origin_kind="unknown",
                    notes="Provider provenance is retained. Source independence is unresolved until a citation or shared origin is found.",
                )
            )
            export.candidates.append(
                EvidenceCandidate(
                    id=stable_id("cand", document.id),
                    document_id=document.id,
                    url=document.canonical_url,
                    title=document.title,
                    snippet=merged.snippet,
                    providers=list(merged.providers),
                    attention=attention,
                    publish_date=merged.publish_date,
                )
            )
            batches.append(self._extract_page(investigation, guard, document, version))
        if not batches:
            return
        merged_batch = merge_batches(batches)
        export.entities.extend(merged_batch.entities)
        export.claims.extend(merged_batch.claims)
        export.relationships.extend(merged_batch.relationships)
        export.evidence_spans.extend(merged_batch.spans)
        export.evidence_links.extend(merged_batch.links)
        export.unresolved_questions.extend(merged_batch.questions)
        investigation.usage.rejected_ungrounded_citations += merged_batch.rejected_ungrounded
        if merged_batch.live_extraction_blocked and not merged_batch.relationships:
            investigation.live_extraction_blocked = True
            investigation.blocker = merged_batch.blocker
        if merged_batch.llm_tokens is not None:
            investigation.usage.llm_tokens = (investigation.usage.llm_tokens or 0) + merged_batch.llm_tokens

    def _extract_page(self, investigation: Investigation, guard: BudgetGuard, document: Document, version: DocumentVersion) -> ExtractionBatch:
        disclosed = extract_document(
            version.content,
            url=document.canonical_url,
            document_id=document.id,
            version_id=version.id,
            version_hash=version.content_hash,
            question=investigation.question,
            publish_date=version.publish_date,
            llm=OpenAICompatibleClient(api_key=""),
        )
        if disclosed.relationships or not llm_api_key():
            return disclosed
        try:
            guard.authorize_llm()
        except BudgetExceededError:
            return disclosed
        investigation.budget = guard.budget
        investigation.usage.llm_calls += 1
        return extract_document(
            version.content,
            url=document.canonical_url,
            document_id=document.id,
            version_id=version.id,
            version_hash=version.content_hash,
            question=investigation.question,
            publish_date=version.publish_date,
        )

    def _stop_budget(self, export: ExplorationExport, guard: BudgetGuard) -> ExplorationExport:
        export.investigation.budget = guard.budget
        export.investigation.status = "stopped"
        export.investigation.stop_reason = "budget_exhausted"
        export.investigation.decision_rationale = "Backend refused another search because the hard cap is 2 searches."
        export.investigation.updated_at = _now()
        self._persist(export)
        save_checkpoint(self.database, export, step=export.investigation.usage.search_calls + 1, summary="Refused a search past the hard cap.", stop_reason="budget_exhausted")
        return self.graph.load(export.investigation.id)

    def _persist(self, export: ExplorationExport) -> None:
        self.graph.save(export)


def _candidate(question: str, document: Document, version: DocumentVersion, questions: list[UnresolvedQuestion]) -> EvidenceCandidate:
    attention = score_passage(
        question,
        version.content[:1500],
        [item.text for item in questions],
        version.publish_date,
    )
    return EvidenceCandidate(
        id=stable_id("cand", document.id),
        document_id=document.id,
        url=document.canonical_url,
        title=document.title,
        snippet=version.content[:280].replace("\n", " "),
        providers=list(document.providers),
        attention=attention,
        publish_date=version.publish_date,
    )


def is_fixture_url(url: str) -> bool:
    return ".example/" in url or url.endswith(".example")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_seconds() -> float:
    return datetime.now(timezone.utc).timestamp()


def _elapsed_ms(started: float) -> int:
    return max(0, int((datetime.now(timezone.utc).timestamp() - started) * 1000))
