"""Deterministic exploration tests. No network."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from exploration.backend.attention import score_passage
from exploration.backend.budget import BudgetExceededError, BudgetGuard, clamp_budget
from exploration.backend.checkpoints import list_checkpoints
from exploration.backend.convergence import build_request, evaluate_controller
from exploration.backend.extraction import relationships_from_llm_payload
from exploration.backend.main import create_app
from exploration.backend.orchestrator import Orchestrator
from exploration.backend.planner import fallback_decision, generate_actions
from exploration.backend.retrieval import ProviderHit, merge_provider_hits, normalize_url
from exploration.backend.verification import assess_quotation, classify_provenance, origin_clusters
from shared.contracts import (
    CONTRACT_VERSION,
    ExplorationExport,
    InvestigationAction,
    InvestigationBudget,
    Relationship,
    UnresolvedQuestion,
    UsageMetrics,
    evidence_json_schema,
)


def test_story_a_search_query_stays_separate_from_the_question():
    from exploration.backend.orchestrator import STORY_A_QUESTION
    from exploration.backend.planner import initial_search_query

    query = initial_search_query(STORY_A_QUESTION)
    assert query != STORY_A_QUESTION
    assert "CoreWeave" in query
    assert len(query) < 120
    assert initial_search_query("battery degradation resale value") == "battery degradation resale value"


def test_normalize_url_strips_fragment_slash_and_lowercases_host():
    assert normalize_url("HTTPS://Example.COM/a/b/#frag") == "https://example.com/a/b"
    assert normalize_url("https://example.com/") == "https://example.com/"
    assert normalize_url("https://example.com/a/?q=1#x") == "https://example.com/a?q=1"


def test_provider_dedup_keeps_both_providers_as_one_document():
    hits = [
        ProviderHit(provider="brave", url="https://Example.com/a/#x", canonical_url="https://example.com/a", title="A"),
        ProviderHit(provider="tavily", url="https://example.com/a/", canonical_url="https://example.com/a", title="A"),
    ]
    documents = merge_provider_hits(hits)
    assert len(documents) == 1
    assert documents[0].providers == ["brave", "tavily"]
    assert len(documents[0].hits) == 2


def test_attention_components_stay_in_unit_interval_and_are_not_confidence():
    scored = score_passage(
        "NVIDIA investment capacity",
        "NVIDIA investment in capacity and CoreWeave demand",
        gaps=["downstream product demand"],
        publish_date="2026-11-01",
    )
    for value in (scored.R, scored.G, scored.D, scored.F, scored.score):
        assert 0.0 <= value <= 1.0
    expected = 0.4 * scored.R + 0.3 * scored.G + 0.2 * scored.D + 0.1 * scored.F
    assert scored.score == pytest.approx(min(1.0, expected))
    assert "confidence" in scored.model_fields["score"].description.lower() or "not" in scored.model_fields["score"].description.lower()


def test_quote_must_be_an_exact_substring():
    content = "Lumenarc Dynamics closed a $400 million Series D."
    good = assess_quotation(content, "$400 million")
    bad = assess_quotation(content, "$480 million")
    assert good.valid and good.start == content.find("$400 million")
    assert content[good.start : good.end] == "$400 million"
    assert not bad.valid and bad.start is None


def test_ungrounded_llm_relationship_is_insufficient():
    content = "Lumenarc Dynamics closed a $400 million Series D."
    batch = relationships_from_llm_payload(
        {
            "relationships": [
                {
                    "subject": "Lumenarc Dynamics",
                    "predicate": "raised_amount",
                    "object": "$480 million",
                    "quote": "closed a $480 million Series D",
                    "status": "supported",
                }
            ]
        },
        content,
        document_id="doc",
        version_id="ver",
        version_hash="hash",
    )
    assert batch.rejected_ungrounded == 1
    assert batch.relationships[0].status == "insufficient"
    assert all(rel.status != "supported" for rel in batch.relationships)


def test_relationship_schema_rejects_unknown_status():
    with pytest.raises(Exception):
        Relationship(
            id="rel",
            subject_id="a",
            predicate="raised_amount",
            object_id="b",
            status="confirmed",
        )


def test_provenance_does_not_call_derivatives_independent():
    original = "FOR IMMEDIATE RELEASE\nWire ID: LF-PR-2026-031\nclosed a $400 million Series D."
    derivative = "according to wire ID LF-PR-2026-031 and https://lumenarc.example/press/2026-03-04-helios-array"
    unknown = "A company announced something with no citation."
    original_prov = classify_provenance("doc-o", "https://lumenarc.example/press/2026-03-04-helios-array", original, ["fixture"])
    derivative_prov = classify_provenance("doc-d", "https://voltstreet.example/markets/lumenarc", derivative, ["brave", "tavily"])
    unknown_prov = classify_provenance("doc-u", "https://example.com/other", unknown, ["brave"])
    assert original_prov.origin_kind == "original"
    assert derivative_prov.origin_kind == "derivative"
    assert derivative_prov.shared_origin_group == "LF-PR-2026-031"
    assert unknown_prov.origin_kind == "unknown"
    assert "not independent" in unknown_prov.notes
    clusters = origin_clusters([original_prov, derivative_prov, unknown_prov])
    assert len(clusters) == 1
    assert clusters[0].original_document_ids == ["doc-o"]
    assert clusters[0].derivative_document_ids == ["doc-d"]


def test_budget_refuses_a_third_search_and_a_sixth_url():
    guard = BudgetGuard(clamp_budget(InvestigationBudget(max_searches=99, max_fetched_urls=99, max_llm_calls=99)))
    assert guard.budget.max_searches == 2
    assert guard.budget.max_fetched_urls == 5
    assert guard.budget.max_llm_calls == 10
    guard.authorize_search()
    guard.authorize_search()
    with pytest.raises(BudgetExceededError) as exc:
        guard.authorize_search()
    assert exc.value.kind == "search"
    guard.authorize_fetch(5)
    with pytest.raises(BudgetExceededError):
        guard.authorize_fetch(1)
    with pytest.raises(BudgetExceededError) as batch:
        BudgetGuard(clamp_budget(None)).authorize_fetch(6)
    assert batch.value.kind == "fetch_batch"


def test_checkpoint_persists_and_resume_does_not_refetch(tmp_path: Path):
    orchestrator = Orchestrator(tmp_path / "story.sqlite")
    export = orchestrator.run_story_c()
    checkpoints = list_checkpoints(orchestrator.database, export.investigation.id)
    assert len(checkpoints) >= 2
    assert checkpoints[-1].state_json["question"] == export.investigation.question
    before = orchestrator.retrieval.session_id
    stats = orchestrator.resume(export.investigation.id)
    assert stats["network_fetches"] == 0
    assert stats["unchanged_versions"] == len(export.document_versions)
    assert orchestrator.retrieval.session_id == before
    reloaded = orchestrator.get(export.investigation.id)
    assert reloaded.investigation.question == export.investigation.question
    assert len(reloaded.document_versions) == len(export.document_versions)


def test_convergence_request_round_trip_and_fallback(tmp_path: Path):
    question = UnresolvedQuestion(id="q1", text="independent confirmation of the amount", importance=0.9, missing_evidence=1.0, kind="independence")
    action = generate_actions([question], [])[0]
    request = build_request(
        investigation_id="inv",
        question="original question stays immutable",
        questions=[question],
        candidates=[],
        actions=[action],
        budget=InvestigationBudget(),
        usage=UsageMetrics(),
    )
    assert request.contract_version == CONTRACT_VERSION
    assert request.original_question == "original question stays immutable"

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "stop": False,
                "rationale": "Controller approved the independence query.",
                "approved_action": action.model_dump(),
            }

    decision = evaluate_controller(request, followups_executed=0, post=lambda *args, **kwargs: Response())
    assert decision.decision_source == "convergence"
    assert decision.approved_action is not None
    assert decision.approved_action.query == action.query

    fallback = evaluate_controller(
        request,
        followups_executed=0,
        post=lambda *args, **kwargs: (_ for _ in ()).throw(ConnectionError("down")),
    )
    assert fallback.decision_source == "fallback"
    assert fallback.stop is False
    assert fallback.approved_action is not None

    stopped = fallback_decision(
        investigation_id="inv",
        questions=[question],
        actions=[action],
        budget=InvestigationBudget(searches_used=2, max_searches=2),
        followups_executed=0,
        error_type="ConnectError",
    )
    assert stopped.decision_source == "fallback"
    assert stopped.stop_reason == "budget_exhausted"


def test_story_c_finds_shared_origin_and_contradiction(tmp_path: Path):
    orchestrator = Orchestrator(tmp_path / "storyc.sqlite", post=lambda *args, **kwargs: (_ for _ in ()).throw(ConnectionError("down")))
    export = orchestrator.run_story_c()
    assert export.investigation.usage.network_calls == 0
    assert export.investigation.decision_source == "fallback"
    assert any(cluster.origin_id == "LF-PR-2026-031" and len(cluster.document_ids) == 4 for cluster in export.origin_clusters)
    assert any(item.origin_kind == "original" for item in export.provenance)
    assert sum(item.origin_kind == "derivative" for item in export.provenance) == 3
    contradicted = [rel for rel in export.relationships if rel.status == "contradicted"]
    assert contradicted
    assert any("$480 million" in rel.object_name for rel in contradicted)
    supported = [rel for rel in export.relationships if rel.status == "supported" and rel.predicate == "raised_amount"]
    assert supported
    assert all("$400 million" in rel.object_name for rel in supported)
    for span in export.evidence_spans:
        version = next(item for item in export.document_versions if item.id == span.version_id)
        assert version.content[span.start : span.end] == span.text


def test_story_c_http_endpoint(tmp_path: Path):
    app = create_app(tmp_path / "api.sqlite")
    client = TestClient(app)
    response = client.post("/api/exploration/fixtures/story-c")
    assert response.status_code == 200
    payload = response.json()
    ExplorationExport.model_validate(payload)
    assert payload["investigation"]["usage"]["network_calls"] == 0
    assert payload["contradictions"]


def test_export_schema_covers_the_contract():
    schema = evidence_json_schema()
    defs = schema.get("$defs") or schema.get("definitions") or {}
    for name in (
        "Investigation",
        "InvestigationBudget",
        "Document",
        "DocumentVersion",
        "EvidenceSpan",
        "Entity",
        "Claim",
        "Relationship",
        "EvidenceLink",
        "SourceProvenance",
        "UnresolvedQuestion",
        "EvidenceCandidate",
        "ConvergenceDecision",
        "InvestigationAction",
        "Checkpoint",
        "UsageMetrics",
    ):
        assert name in defs
    assert "question" in defs["Investigation"]["properties"]
