"""One exploration export handed to the focus ranker through the existing contract."""

from __future__ import annotations

import json
from pathlib import Path

from exploration.backend.convergence import build_request, evaluate_controller
from exploration.backend.focus_bridge import evaluate_with_focus, focus_http_response
from exploration.backend.orchestrator import Orchestrator
from exploration.backend.retrieval import RetrievalClient
from shared.contracts import (
    ConvergenceEvaluateRequest,
    EvidenceCandidate,
    ExplorationExport,
    InvestigationAction,
    InvestigationBudget,
    UnresolvedQuestion,
    UsageMetrics,
)

ROOT = Path(__file__).resolve().parents[2]


def _post(url, json, timeout):  # noqa: A002 - matches httpx.post
    del url, timeout
    body = focus_http_response(json)

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return body

    return Response()


def test_first_relevant_passage_is_considered_and_does_not_approve_a_search():
    """The new ranker files the first aligned passage as consider, not investigate."""
    request = ConvergenceEvaluateRequest(
        investigation_id="inv_focus",
        original_question="why electric vehicle demand is weakening",
        open_questions=[
            UnresolvedQuestion(
                id="q1",
                text="are battery degradation and resale value affecting purchases",
                importance=0.9,
                missing_evidence=1.0,
            )
        ],
        candidates=[
            EvidenceCandidate(
                id="cand_battery",
                url="https://battery.example/report",
                title="Battery resale",
                snippet="why electric vehicle demand is weakening: battery degradation and resale value affect purchases",
                providers=["tavily"],
                attention={"R": 0.8, "G": 0.2, "D": 0.0, "F": 0.5, "score": 0.4},
            )
        ],
        proposed_actions=[
            InvestigationAction(
                id="act_battery",
                query="battery degradation resale value purchases",
                reason="Open gap.",
                utility=0.9,
            )
        ],
        budget=InvestigationBudget(max_searches=2, searches_used=0),
        usage=UsageMetrics(),
    )
    raw = evaluate_with_focus(request)
    decision = evaluate_controller(request, followups_executed=0, post=_post)
    assert raw["stop"] is True
    assert raw["approved_action"] is None
    assert "cand_battery=consider" in raw["rationale"]
    assert "not verified" in raw["rationale"].lower() or "not verification" in raw["rationale"].lower()
    assert decision.decision_source == "convergence"
    assert decision.stop is True
    assert decision.approved_action is None
    assert decision.stop_reason == "unresolved_uncertainty"


def test_focus_approves_a_search_when_a_later_passage_needs_investigation():
    request = ConvergenceEvaluateRequest(
        investigation_id="inv_focus",
        original_question="why electric vehicle demand is weakening",
        open_questions=[
            UnresolvedQuestion(
                id="q1",
                text="are battery degradation and resale value affecting purchases",
                importance=0.9,
                missing_evidence=1.0,
            )
        ],
        candidates=[
            EvidenceCandidate(
                id="seed",
                url="https://x.example/seed",
                title="Seed",
                snippet="why electric vehicle demand is weakening",
                providers=["fixture"],
                attention={"R": 1.0, "G": 0.0, "D": 0.0, "F": 0.0, "score": 0.4},
            ),
            EvidenceCandidate(
                id="battery",
                url="https://battery.example/report",
                title="Battery",
                snippet="electric vehicle demand battery resale",
                providers=["tavily"],
                attention={"R": 0.5, "G": 0.2, "D": 0.0, "F": 0.0, "score": 0.3},
            ),
        ],
        proposed_actions=[
            InvestigationAction(
                id="act_battery",
                query="battery degradation resale value purchases",
                reason="Open gap.",
                utility=0.9,
            )
        ],
        budget=InvestigationBudget(max_searches=2, searches_used=0),
        usage=UsageMetrics(),
    )
    raw = evaluate_with_focus(request)
    decision = evaluate_controller(request, followups_executed=0, post=_post)
    assert raw["stop"] is False
    assert decision.decision_source == "convergence"
    assert decision.stop is False
    assert decision.approved_action is not None
    assert decision.approved_action.id == "act_battery"
    assert decision.include_document_ids == ["battery"]


def test_focus_refuses_a_search_when_the_budget_is_spent():
    request = ConvergenceEvaluateRequest(
        investigation_id="inv_budget",
        original_question="why electric vehicle demand is weakening",
        budget=InvestigationBudget(max_searches=2, searches_used=2),
        usage=UsageMetrics(),
    )
    decision = evaluate_controller(request, followups_executed=0, post=_post)
    assert decision.decision_source == "convergence"
    assert decision.stop is True
    assert decision.stop_reason == "budget_exhausted"
    assert decision.approved_action is None


def test_story_c_handoff_keeps_exact_quotes_and_labels_the_extractor(tmp_path):
    orchestrator = Orchestrator(tmp_path / "story.sqlite", post=_post)
    export = orchestrator.run_story_c()
    loaded = ExplorationExport.model_validate(export.model_dump(mode="json"))
    assert loaded.investigation.metadata["extraction_origin"] == "deterministic_fixture"
    assert loaded.investigation.metadata["llm_relationships"] == 0
    assert loaded.investigation.usage.network_calls == 0
    assert loaded.investigation.usage.llm_calls == 0
    assert loaded.investigation.decision_source == "convergence"
    assert loaded.decision is not None
    assert loaded.decision.decision_source == "convergence"
    assert loaded.checkpoints
    versions = {version.document_id: version for version in loaded.document_versions}
    links = {link.relationship_id: link for link in loaded.evidence_links}
    spans = {span.id: span for span in loaded.evidence_spans}
    harbor_supported = False
    for rel in loaded.relationships:
        if rel.status not in {"supported", "contradicted"}:
            continue
        link = links[rel.id]
        span = spans[link.evidence_span_id]
        version = versions[rel.document_id]
        assert version.content[span.start : span.end] == span.text
        assert link.quote_valid is True
        document = next(item for item in loaded.documents if item.id == rel.document_id)
        if "harbor" in document.canonical_url and rel.predicate == "raised_amount" and rel.status == "supported":
            harbor_supported = True
            assert "$400 million" in span.text
            assert "Lumenarc Dynamics" in span.text
            assert "independent" not in rel.notes.lower()
        if rel.object_name == "$480 million":
            assert rel.status == "contradicted"
    assert harbor_supported
    request = build_request(
        investigation_id=loaded.investigation.id,
        question=loaded.investigation.question,
        questions=loaded.unresolved_questions,
        candidates=loaded.candidates,
        actions=loaded.actions,
        budget=loaded.investigation.budget,
        usage=loaded.investigation.usage,
    )
    again = ConvergenceEvaluateRequest.model_validate(request.model_dump(mode="json"))
    assert again.original_question == loaded.investigation.question
    assert {entity.id for entity in loaded.entities}
    resume = orchestrator.resume(loaded.investigation.id)
    assert resume["network_fetches"] == 0
    record = json.loads((ROOT / "demo" / "evaluation.json").read_text(encoding="utf-8"))
    pairs = {(row["predicate"], row["object"]) for row in record["story_a"]["relationships"]}
    assert len(record["story_a"]["relationships"]) == 6
    assert pairs == {("invested_in", "CoreWeave"), ("invested_amount", "$2 billion")}
    assert record["story_a"]["demonstration"] == "precomputed"


def test_integrated_investigation_resumes_without_repeating_retrieval(tmp_path, monkeypatch):
    monkeypatch.setenv("TELEM_API_KEY", "resume-dummy")
    calls = {"search": 0, "fetch": 0}
    page = "NVIDIA has invested $2 billion in CoreWeave."

    def search_fn(query, session_id):
        del query, session_id
        calls["search"] += 1
        return {
            "session_id": "sess-resume",
            "interaction_id": "int-resume",
            "by_provider": [
                {
                    "provider": "brave",
                    "status": "ok",
                    "results": [
                        {
                            "provider": "brave",
                            "url": "https://example.com/nvidia",
                            "title": "NVIDIA CoreWeave",
                            "snippet": page,
                            "publish_date": "2026-01-15",
                        }
                    ],
                }
            ],
        }

    def fetch_fn(urls, session_id):
        del session_id
        calls["fetch"] += 1
        return {"results": [{"url": urls[0], "content": page, "status": "ok", "provider": "telem"}]}

    db_path = tmp_path / "integrated.sqlite"
    cache = tmp_path / "cache"
    first = Orchestrator(
        db_path,
        retrieval=RetrievalClient(
            cache_dir=cache,
            dry_run=False,
            search_fn=search_fn,
            fetch_fn=fetch_fn,
            sleeper=lambda _seconds: None,
            tavily_extract_fn=lambda _url: "",
        ),
        post=_post,
    )
    created = first.create("alpha beta gamma delta", mode="web")
    first.step(created.id)
    finished = first.step(created.id)
    assert calls["search"] >= 1
    assert calls["fetch"] >= 1
    assert finished.investigation.decision_source == "convergence"
    assert finished.decision is not None
    assert finished.decision.rationale
    searches_used = finished.investigation.budget.searches_used
    urls_fetched = finished.investigation.budget.urls_fetched
    completed_searches = calls["search"]
    completed_fetches = calls["fetch"]
    first.database.close()

    def repeated_search(*_args, **_kwargs):
        calls["search"] += 1
        raise AssertionError("resume repeated a completed search")

    def repeated_fetch(*_args, **_kwargs):
        calls["fetch"] += 1
        raise AssertionError("resume repeated a completed fetch")

    second = Orchestrator(
        db_path,
        retrieval=RetrievalClient(
            cache_dir=cache,
            dry_run=False,
            search_fn=repeated_search,
            fetch_fn=repeated_fetch,
            sleeper=lambda _seconds: None,
            tavily_extract_fn=lambda _url: "",
        ),
        post=_post,
    )
    loaded = second.get(created.id)
    latest = loaded.checkpoints[-1]
    assert latest.state_json["decision_source"] == "convergence"
    assert latest.state_json["decision_rationale"] == finished.decision.rationale
    assert latest.state_json["decision"]["rationale"] == finished.decision.rationale
    assert latest.state_json["decision"]["decision_source"] == "convergence"
    assert latest.state_json["budget"]["searches_used"] == searches_used
    assert loaded.decision is not None
    assert loaded.decision.rationale == finished.decision.rationale
    assert len(loaded.documents) == len(finished.documents)
    assert len(loaded.relationships) == len(finished.relationships)
    stats = second.resume(created.id)
    assert stats["network_fetches"] == 0
    assert calls["search"] == completed_searches
    assert calls["fetch"] == completed_fetches
    reloaded = second.get(created.id)
    assert reloaded.investigation.budget.searches_used == searches_used
    assert reloaded.investigation.budget.urls_fetched == urls_fetched
    assert reloaded.investigation.question == finished.investigation.question
