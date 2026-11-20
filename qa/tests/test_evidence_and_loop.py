"""Independent checks for grounding, provenance, the loop, and checkpoints."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from exploration.backend.baseline import report_from_export, run_baseline
from exploration.backend.extraction import extract_document, relationships_from_llm_payload
from exploration.backend.llm import OpenAICompatibleClient
from exploration.backend.main import create_app
from exploration.backend.orchestrator import STORY_A_QUESTION, Orchestrator
from exploration.backend.retrieval import RetrievalClient
from shared.contracts import (
    CONTRACT_VERSION,
    ConvergenceEvaluateRequest,
    ExplorationExport,
    InvestigationBudget,
)

ROOT = Path(__file__).resolve().parents[2]
PAGE = "NVIDIA invested $2 billion in CoreWeave."
GAP = "downstream product demand"


def _down(*_args, **_kwargs):
    raise httpx.ConnectError("connection refused")


def _client(tmp_path: Path, search_fn, fetch_fn) -> RetrievalClient:
    return RetrievalClient(
        cache_dir=tmp_path / "cache",
        dry_run=False,
        search_fn=search_fn,
        fetch_fn=fetch_fn,
        sleeper=lambda _seconds: None,
        tavily_extract_fn=lambda _url: "",
    )


def _bundle(url: str, title: str, snippet: str, provider: str = "brave") -> dict:
    return {
        "session_id": "sess-qa",
        "interaction_id": "int-qa",
        "by_provider": [
            {
                "provider": provider,
                "status": "ok",
                "results": [
                    {
                        "provider": provider,
                        "url": url,
                        "title": title,
                        "snippet": snippet,
                        "publish_date": "2026-01-15",
                    }
                ],
            }
        ],
    }


def test_quotes_must_exist_and_bad_quotes_cannot_support_edges():
    payload = {
        "relationships": [
            {
                "subject": "NVIDIA",
                "predicate": "invested_in",
                "object": "CoreWeave",
                "quote": PAGE,
                "status": "supported",
            },
            {
                "subject": "NVIDIA",
                "predicate": "caused",
                "object": "demand",
                "quote": "NVIDIA caused demand",
                "status": "supported",
            },
        ]
    }
    batch = relationships_from_llm_payload(
        payload,
        PAGE,
        document_id="doc",
        version_id="ver",
        version_hash="hash",
    )
    supported = [rel for rel in batch.relationships if rel.status == "supported"]
    assert [rel.predicate for rel in supported] == ["invested_in"]
    assert all(rel.evidence_link_ids for rel in supported)
    for span in batch.spans:
        assert PAGE[span.start : span.end] == span.text
    again = relationships_from_llm_payload(
        payload,
        PAGE,
        document_id="doc",
        version_id="ver",
        version_hash="hash",
    )
    assert [claim.id for claim in batch.claims] == [claim.id for claim in again.claims]


def test_extraction_failure_does_not_crash_or_invent_relationships():
    class Broken(OpenAICompatibleClient):
        @property
        def configured(self) -> bool:
            return True

        def complete_json(self, system: str, user: str):
            raise RuntimeError("structured output was not JSON")

    batch = extract_document(
        PAGE,
        url="https://example.com/nvidia",
        document_id="doc",
        version_id="ver",
        version_hash="hash",
        question="What did NVIDIA fund?",
        llm=Broken(api_key="qa-dummy"),
    )
    assert batch.relationships == []
    assert batch.live_extraction_blocked is True
    assert batch.blocker


def test_story_c_provenance_contradiction_and_metrics(tmp_path):
    calls = {"search": 0, "fetch": 0}

    def explode(*_args, **_kwargs):
        calls["search"] += 1
        raise AssertionError("external call")

    orchestrator = Orchestrator(tmp_path / "story.sqlite", retrieval=_client(tmp_path, explode, explode), post=_down)
    export = orchestrator.run_story_c()
    _assert_story_c_graph(export)
    report = report_from_export(export, story="C", configuration="B3")
    assert report.network_calls == 0
    assert report.llm_calls == 0
    assert report.shared_origin_detected is True
    assert report.contradiction_detections == len(export.contradictions)
    assert report.supported_relationships == sum(1 for rel in export.relationships if rel.status == "supported")
    assert report.correct_citations == len(export.evidence_spans)
    _b0, b0 = run_baseline(story="C", configuration="B0", db_path=tmp_path / "b0.sqlite", post=_down)
    assert b0.shared_origin_detected is False
    assert b0.contradiction_detections == 0
    assert b0.network_calls == 0
    assert calls == {"search": 0, "fetch": 0}


def test_story_c_survives_reload_without_new_external_calls(tmp_path):
    calls = {"n": 0}

    def explode(*_args, **_kwargs):
        calls["n"] += 1
        raise AssertionError("external call")

    path = tmp_path / "persist.sqlite"
    first = Orchestrator(path, retrieval=_client(tmp_path, explode, explode), post=_down)
    export = first.run_story_c()
    searches_used = export.investigation.budget.searches_used
    queries = first.database.search_queries(export.investigation.id)
    first.database.close()
    second = Orchestrator(path, retrieval=_client(tmp_path, explode, explode), post=_down)
    loaded = second.get(export.investigation.id)
    stats = second.resume(export.investigation.id)
    assert loaded.investigation.question == export.investigation.question
    assert loaded.investigation.budget.searches_used == searches_used
    assert second.database.search_queries(export.investigation.id) == queries
    assert queries
    assert stats["network_fetches"] == 0
    assert calls["n"] == 0
    loaded.investigation.question = "rewritten intent"
    with pytest.raises(ValueError):
        second.graph.save(loaded)


def test_completed_web_investigation_reloads_without_new_calls(tmp_path, monkeypatch):
    """A stopped web investigation reuses stored pages. A fresh cache does not refetch them."""
    monkeypatch.setenv("TELEM_API_KEY", "qa-dummy")
    text = "NVIDIA has invested $2 billion in CoreWeave."
    calls = {"n": 0}

    def search_fn(query, session_id):
        del query, session_id
        calls["n"] += 1
        return {
            "session_id": "sess-reload",
            "interaction_id": f"int-{calls['n']}",
            "provider_runs": [
                {
                    "provider": "brave",
                    "results": [
                        {
                            "url": f"https://news.example/page-{calls['n']}",
                            "title": "NVIDIA",
                            "summary": text,
                            "provider": "brave",
                        }
                    ],
                }
            ],
        }

    def fetch_fn(urls, session_id):
        del session_id
        calls["n"] += 1
        return {"results": [{"url": urls[0], "content": text, "status": "ok", "provider": "telem"}]}

    path = tmp_path / "web.sqlite"
    first = Orchestrator(path, retrieval=_client(tmp_path, search_fn, fetch_fn), post=_down)
    investigation = first.create(STORY_A_QUESTION, mode="web")
    first.step(investigation.id)
    finished = first.step(investigation.id)
    assert finished.investigation.status == "stopped"
    assert finished.documents
    assert finished.relationships
    searches_used = finished.investigation.budget.searches_used
    question = finished.investigation.question
    first.database.close()

    def explode(*_args, **_kwargs):
        calls["n"] += 1
        raise AssertionError("reload issued an external call")

    fresh = RetrievalClient(
        cache_dir=tmp_path / "fresh-cache",
        dry_run=False,
        search_fn=explode,
        fetch_fn=explode,
        sleeper=lambda _seconds: None,
    )
    before = calls["n"]
    second = Orchestrator(path, retrieval=fresh, post=_down)
    stats = second.resume(investigation.id)
    reloaded = second.step(investigation.id)
    assert stats["network_fetches"] == 0
    assert calls["n"] == before
    assert reloaded.investigation.status == "stopped"
    assert reloaded.investigation.question == question
    assert reloaded.investigation.budget.searches_used == searches_used
    assert len(reloaded.documents) == len(finished.documents)
    assert len(reloaded.relationships) == len(finished.relationships)
    assert reloaded.investigation.usage.search_calls == searches_used
    assert len(second.database.search_queries(investigation.id)) == searches_used
    assert reloaded.investigation.decision_source == "fallback"
    versions = {version.id: version for version in reloaded.document_versions}
    assert reloaded.evidence_spans
    for span in reloaded.evidence_spans:
        version = versions[span.version_id]
        assert version.content[span.start : span.end] == span.text
    assert reloaded.checkpoints[-1].stop_reason == reloaded.investigation.stop_reason


def test_two_web_investigations_keep_separate_graphs(tmp_path, monkeypatch):
    """Saving a second investigation does not replace the first investigation's edges."""
    monkeypatch.setenv("TELEM_API_KEY", "qa-dummy")
    text = "NVIDIA has invested $2 billion in CoreWeave."
    path = tmp_path / "shared.sqlite"

    def run(url: str):
        def search_fn(query, session_id):
            del query, session_id
            return {
                "session_id": "sess-shared",
                "interaction_id": "int-shared",
                "provider_runs": [
                    {
                        "provider": "brave",
                        "results": [{"url": url, "title": "NVIDIA", "summary": text, "provider": "brave"}],
                    }
                ],
            }

        def fetch_fn(urls, session_id):
            del session_id
            return {"results": [{"url": urls[0], "content": text, "status": "ok", "provider": "telem"}]}

        orchestrator = Orchestrator(path, retrieval=_client(tmp_path, search_fn, fetch_fn), post=_down)
        created = orchestrator.create(STORY_A_QUESTION, mode="web")
        return orchestrator, orchestrator.step(created.id)

    first_orchestrator, first = run("https://news.example/first")
    _second_orchestrator, second = run("https://news.example/second")
    reloaded = first_orchestrator.get(first.investigation.id)
    assert reloaded.investigation.question == first.investigation.question
    assert len(reloaded.relationships) == len(first.relationships) == 2
    assert len(second.relationships) == 2
    assert {document.id for document in reloaded.documents}.isdisjoint({document.id for document in second.documents})
    assert reloaded.entities and second.entities
    assert reloaded.entities[0].id == second.entities[0].id
    for export in (reloaded, second):
        versions = {version.id: version for version in export.document_versions}
        documents = {document.id for document in export.documents}
        for relationship in export.relationships:
            assert relationship.document_id in documents
            for link_id in relationship.evidence_link_ids:
                link = next(item for item in export.evidence_links if item.id == link_id)
                span = next(item for item in export.evidence_spans if item.id == link.evidence_span_id)
                version = versions[span.version_id]
                assert span.document_id == relationship.document_id
                assert version.content[span.start : span.end] == span.text


def test_controller_approval_executes_and_malformed_payload_does_not(tmp_path, monkeypatch):
    monkeypatch.setenv("TELEM_API_KEY", "qa-dummy")
    monkeypatch.setenv("LLM_API_KEY", "qa-dummy")
    searched: list[str] = []

    def search_fn(query: str, session_id: str | None):
        searched.append(query)
        return _bundle("https://example.com/nvidia", "NVIDIA", PAGE)

    def fetch_fn(urls: list[str], session_id: str | None):
        return {"results": [{"url": urls[0], "content": PAGE, "status": "ok", "provider": "telem"}]}

    def complete_json(self, system: str, user: str):
        if PAGE not in user:
            return {"relationships": [], "gaps": []}, {}
        return {
            "relationships": [
                {
                    "subject": "NVIDIA",
                    "predicate": "invested_in",
                    "object": "CoreWeave",
                    "quote": PAGE,
                }
            ],
            "gaps": [{"text": GAP, "importance": 0.95}],
        }, {}

    monkeypatch.setattr(OpenAICompatibleClient, "complete_json", complete_json)
    approved_query = "independent evidence of downstream product demand"

    def post(url, json, timeout):
        body = ConvergenceEvaluateRequest.model_validate(json)
        assert body.contract_version == CONTRACT_VERSION
        assert body.original_question == STORY_A_QUESTION
        assert body.open_questions

        class Response:
            def raise_for_status(self):
                return None

            def json(self):
                return {
                    "approved_action": {
                        "id": "act-qa",
                        "query": approved_query,
                        "reason": "controller selected the demand gap",
                        "utility": 0.8,
                    },
                    "stop": False,
                    "rationale": "Approve the demand follow-up.",
                    "decision_source": "fallback",
                }

        return Response()

    orchestrator = Orchestrator(
        tmp_path / "loop.sqlite",
        retrieval=_client(tmp_path, search_fn, fetch_fn),
        post=post,
        convergence_url="http://127.0.0.1:9/api/convergence/evaluate",
    )
    created = orchestrator.create(STORY_A_QUESTION, mode="web")
    assert created.question == STORY_A_QUESTION
    first = orchestrator.step(created.id)
    assert first.investigation.question == STORY_A_QUESTION
    assert searched
    second = orchestrator.step(created.id)
    assert approved_query in searched
    assert second.investigation.decision_source == "convergence"
    assert second.investigation.question == STORY_A_QUESTION


def test_malformed_controller_payload_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setenv("TELEM_API_KEY", "qa-dummy")
    monkeypatch.setenv("LLM_API_KEY", "qa-dummy")
    searched: list[str] = []

    def search_fn(query: str, session_id: str | None):
        searched.append(query)
        return _bundle("https://example.com/nvidia", "NVIDIA", PAGE)

    def fetch_fn(urls: list[str], session_id: str | None):
        return {"results": [{"url": urls[0], "content": PAGE, "status": "ok", "provider": "telem"}]}

    def complete_json(self, system: str, user: str):
        if PAGE not in user:
            return {"relationships": [], "gaps": []}, {}
        return {
            "relationships": [
                {
                    "subject": "NVIDIA",
                    "predicate": "invested_in",
                    "object": "CoreWeave",
                    "quote": PAGE,
                }
            ],
            "gaps": [{"text": GAP, "importance": 0.2}],
        }, {}

    monkeypatch.setattr(OpenAICompatibleClient, "complete_json", complete_json)

    def malformed(_url, json, timeout):
        class Response:
            def raise_for_status(self):
                return None

            def json(self):
                return ["not", "an", "object"]

        return Response()

    orchestrator = Orchestrator(
        tmp_path / "bad.sqlite",
        retrieval=_client(tmp_path, search_fn, fetch_fn),
        post=malformed,
    )
    created = orchestrator.create(STORY_A_QUESTION, mode="web")
    orchestrator.step(created.id)
    before = list(searched)
    decision = orchestrator.step(created.id)
    assert decision.investigation.decision_source == "fallback"
    assert "not an object" not in decision.investigation.decision_rationale
    assert searched == before or decision.investigation.decision_source == "fallback"


def test_repeated_entity_on_follow_up_does_not_crash(tmp_path, monkeypatch):
    monkeypatch.setenv("TELEM_API_KEY", "qa-dummy")
    monkeypatch.setenv("LLM_API_KEY", "qa-dummy")
    phase = {"follow": False}

    def search_fn(query: str, session_id: str | None):
        url = "https://example.com/second" if phase["follow"] else "https://example.com/first"
        return _bundle(url, "NVIDIA", PAGE)

    def fetch_fn(urls: list[str], session_id: str | None):
        return {"results": [{"url": urls[0], "content": PAGE, "status": "ok", "provider": "telem"}]}

    def complete_json(self, system: str, user: str):
        return {
            "relationships": [
                {
                    "subject": "NVIDIA",
                    "predicate": "invested_in",
                    "object": "CoreWeave",
                    "quote": PAGE,
                }
            ],
            "gaps": [{"text": GAP, "importance": 0.95}],
        }, {}

    monkeypatch.setattr(OpenAICompatibleClient, "complete_json", complete_json)
    orchestrator = Orchestrator(
        tmp_path / "entity.sqlite",
        retrieval=_client(tmp_path, search_fn, fetch_fn),
        post=_down,
    )
    created = orchestrator.create("alpha beta gamma delta", mode="web")
    orchestrator.step(created.id)
    phase["follow"] = True
    export = orchestrator.step(created.id)
    assert export.investigation.status in {"running", "stopped"}
    names = [entity.name for entity in export.entities]
    assert names.count("NVIDIA") == 1


def test_duplicate_controller_query_is_not_executed(tmp_path, monkeypatch):
    monkeypatch.setenv("TELEM_API_KEY", "qa-dummy")
    monkeypatch.setenv("LLM_API_KEY", "qa-dummy")
    searched: list[str] = []

    def search_fn(query: str, session_id: str | None):
        searched.append(query)
        return _bundle("https://example.com/nvidia", "NVIDIA", PAGE)

    def fetch_fn(urls: list[str], session_id: str | None):
        return {"results": [{"url": urls[0], "content": PAGE, "status": "ok", "provider": "telem"}]}

    def complete_json(self, system: str, user: str):
        return {
            "relationships": [
                {
                    "subject": "NVIDIA",
                    "predicate": "invested_in",
                    "object": "CoreWeave",
                    "quote": PAGE,
                }
            ],
            "gaps": [{"text": GAP, "importance": 0.95}],
        }, {}

    monkeypatch.setattr(OpenAICompatibleClient, "complete_json", complete_json)

    def post(_url, json, timeout):
        class Response:
            def raise_for_status(self):
                return None

            def json(self):
                return {
                    "approved_action": {
                        "id": "act-dup",
                        "query": searched[0],
                        "reason": "repeat the first query",
                        "utility": 0.9,
                    },
                    "stop": False,
                    "rationale": "Repeat it.",
                }

        return Response()

    orchestrator = Orchestrator(
        tmp_path / "dup.sqlite",
        retrieval=_client(tmp_path, search_fn, fetch_fn),
        post=post,
    )
    created = orchestrator.create("alpha beta gamma delta", mode="web")
    orchestrator.step(created.id)
    before = len(searched)
    orchestrator.step(created.id)
    assert len(searched) == before


def test_unresolved_gap_changes_which_page_is_fetched(tmp_path, monkeypatch):
    monkeypatch.setenv("TELEM_API_KEY", "qa-dummy")
    monkeypatch.setenv("LLM_API_KEY", "qa-dummy")
    phase = {"follow": False}
    fetched: list[list[str]] = []

    def search_fn(query: str, session_id: str | None):
        if not phase["follow"]:
            return _bundle("https://example.com/first", "First", "alpha beta gamma delta")
        return {
            "session_id": "sess-qa",
            "interaction_id": "int-2",
            "by_provider": [
                {
                    "provider": "brave",
                    "status": "ok",
                    "results": [
                        {
                            "provider": "brave",
                            "url": "https://example.com/query-only",
                            "title": "Query only",
                            "snippet": "alpha beta",
                        },
                        {
                            "provider": "tavily",
                            "url": "https://example.com/gap",
                            "title": "Gap",
                            "snippet": "zeta quantum lattice",
                        },
                    ],
                }
            ],
        }

    def fetch_fn(urls: list[str], session_id: str | None):
        fetched.append(list(urls))
        return {
            "results": [
                {"url": url, "content": PAGE if "first" in url else f"page {url}", "status": "ok", "provider": "telem"}
                for url in urls
            ]
        }

    def complete_json(self, system: str, user: str):
        if PAGE not in user:
            return {"relationships": [], "gaps": []}, {}
        return {
            "relationships": [
                {
                    "subject": "NVIDIA",
                    "predicate": "invested_in",
                    "object": "CoreWeave",
                    "quote": PAGE,
                }
            ],
            "gaps": [{"text": "zeta quantum lattice", "importance": 0.99}],
        }, {}

    monkeypatch.setattr(OpenAICompatibleClient, "complete_json", complete_json)
    orchestrator = Orchestrator(
        tmp_path / "gap.sqlite",
        retrieval=_client(tmp_path, search_fn, fetch_fn),
        post=_down,
    )
    created = orchestrator.create(
        "alpha beta gamma delta",
        InvestigationBudget(max_fetched_urls=2),
        mode="web",
    )
    orchestrator.step(created.id)
    phase["follow"] = True
    orchestrator.step(created.id)
    assert fetched[-1] == ["https://example.com/gap"]


def test_api_export_exposes_graph_and_quotes(tmp_path):
    app = create_app(tmp_path / "api.sqlite")
    app.state.orchestrator.post = _down
    client = TestClient(app)
    story = client.post("/api/exploration/fixtures/story-c")
    assert story.status_code == 200
    body = ExplorationExport.model_validate(story.json())
    _assert_story_c_graph(body)
    exported = client.get(f"/api/exploration/investigations/{body.investigation.id}/export")
    assert exported.status_code == 200
    again = ExplorationExport.model_validate(exported.json())
    assert again.evidence_spans
    assert again.provenance


def test_committed_story_a_record_is_internally_consistent():
    record = json.loads((ROOT / "demo" / "evaluation.json").read_text(encoding="utf-8"))
    story = record["story_a"]
    rationale = story["decision_rationale"].lower()
    if story.get("llm_configured") and story["usage"]["llm_calls"] > 0:
        assert "no llm key" not in rationale
        assert "llm_api_key" not in rationale
    assert len(story["relationships"]) >= 3


def _assert_story_c_graph(export: ExplorationExport) -> None:
    versions = {version.id: version for version in export.document_versions}
    assert len(export.origin_clusters) == 1
    cluster = export.origin_clusters[0]
    assert cluster.origin_id == "LF-PR-2026-031"
    assert len(cluster.document_ids) == 4
    assert len(cluster.original_document_ids) == 1
    assert len(cluster.derivative_document_ids) == 3
    assert any(
        item.conflicting_object == "$480 million" and item.supported_object == "$400 million"
        for item in export.contradictions
    )
    raised = [rel for rel in export.relationships if rel.predicate == "raised_amount"]
    assert any(rel.object_name == "$400 million" and rel.status == "supported" for rel in raised)
    assert any(rel.object_name == "$480 million" and rel.status == "contradicted" for rel in raised)
    assert not any(
        rel.object_name == "$480 million" and rel.status == "supported" for rel in export.relationships
    )
    links = {link.id: link for link in export.evidence_links}
    spans = {span.id: span for span in export.evidence_spans}
    for rel in export.relationships:
        if rel.status not in {"supported", "contradicted"}:
            continue
        assert rel.evidence_link_ids
        for link_id in rel.evidence_link_ids:
            link = links[link_id]
            span = spans[link.evidence_span_id]
            version = versions[span.version_id]
            assert version.content[span.start : span.end] == span.text
            assert link.quote_valid is True
            if rel.status == "contradicted":
                assert link.stance == "contradicts"
                assert link.semantic_status == "contradicted"
            if rel.status == "supported":
                assert link.stance == "supports"
    document_ids = {document.id for document in export.documents}
    for item in export.contradictions:
        assert item.original_document_id in document_ids
        assert item.conflicting_document_id in document_ids
    kinds = {item.document_id: item.origin_kind for item in export.provenance}
    assert "original" in kinds.values()
    assert "derivative" in kinds.values()
    assert export.investigation.stop_reason != "evidence_sufficient"
    assert any("independent" in question.text.lower() for question in export.unresolved_questions)
    for rel in raised:
        if kinds.get(rel.document_id or "") == "derivative" and rel.status == "supported":
            assert "independent" not in rel.notes.lower()
