import httpx
import pytest
from pydantic import ValidationError

from exploration.backend.convergence import decision_from_controller, evaluate_controller
from exploration.backend.extraction import extract_document, relationships_from_llm_payload
from exploration.backend.llm import OpenAICompatibleClient
from exploration.backend.orchestrator import Orchestrator
from exploration.backend.planner import fallback_decision, generate_actions
from exploration.backend.retrieval import RetrievalClient
from exploration.backend.verification import assess_quotation, decide_status
from shared.contracts import (
    ConvergenceEvaluateRequest,
    InvestigationAction,
    InvestigationBudget,
    Relationship,
    UnresolvedQuestion,
)


def _offline_retrieval(tmp_path):
    def explode(*_args, **_kwargs):
        raise AssertionError("network was called")

    return RetrievalClient(
        cache_dir=tmp_path / "cache",
        dry_run=False,
        search_fn=explode,
        fetch_fn=explode,
        sleeper=lambda _seconds: None,
    )


def _down(*_args, **_kwargs):
    raise httpx.ConnectError("connection refused")


def test_quote_must_be_exact_and_ungrounded_is_not_supported():
    content = "The company raised $400 million."
    good = assess_quotation(content, "raised $400 million")
    assert good.valid is True
    assert content[good.start : good.end] == "raised $400 million"
    missing = assess_quotation(content, "raised $999 million")
    assert missing.valid is False
    status, _assessment = decide_status(content, "raised $999 million", "company", "$999 million")
    assert status != "supported"

    payload = {
        "relationships": [
            {"subject": "Acme", "predicate": "owns", "object": "Widget", "quote": "Acme owns Widget", "status": "supported"},
            {"subject": "Acme", "predicate": "acquired", "object": "Globex", "quote": "Acme acquired Globex", "status": "supported"},
        ]
    }
    text = "Acme owns Widget in the report."
    batch = relationships_from_llm_payload(
        payload,
        text,
        document_id="doc",
        version_id="ver",
        version_hash="hash",
    )
    assert any(rel.status == "supported" and rel.predicate == "owns" for rel in batch.relationships)
    assert not any(rel.status == "supported" and rel.predicate == "acquired" for rel in batch.relationships)
    assert all(span.text == text[span.start : span.end] for span in batch.spans)
    assert "Acme acquired Globex" not in {span.text for span in batch.spans}


def test_relationship_schema_and_nvidia_text_is_not_invented():
    Relationship(
        id="rel_1",
        subject_id="ent_a",
        predicate="raised_amount",
        object_id="ent_b",
        status="supported",
    )
    with pytest.raises(ValidationError):
        Relationship(id="rel_2", subject_id="ent_a", predicate="raised_amount", object_id="ent_b", status="maybe")
    blocked = extract_document(
        "NVIDIA invested $2 billion in CoreWeave and announced 5 GW of AI factories.",
        url="https://nvidia.com/news/coreweave",
        document_id="doc_nvidia",
        version_id="ver_nvidia",
        version_hash="hash",
        question="How do NVIDIA's investments reinforce AI capacity?",
        llm=OpenAICompatibleClient(api_key=""),
    )
    assert blocked.relationships == []
    assert blocked.live_extraction_blocked is True
    assert blocked.mode == "blocked"


def test_local_ollama_request_is_not_sent(monkeypatch):
    def refuse(*_args, **_kwargs):
        raise AssertionError("local Ollama was contacted")

    monkeypatch.setattr("httpx.Client.post", refuse)
    blocked = extract_document(
        "NVIDIA invested $2 billion in CoreWeave and announced 5 GW of AI factories.",
        url="https://nvidia.com/news/coreweave",
        document_id="doc_local",
        version_id="ver_local",
        version_hash="hash",
        question="How do NVIDIA's investments reinforce AI capacity?",
        llm=OpenAICompatibleClient(
            api_key="local-test",
            base_url="http://127.0.0.1:11434/v1",
            model="qwen2.5:7b-instruct-q4_K_M",
            timeout=1,
        ),
    )
    assert blocked.relationships == []
    assert blocked.live_extraction_blocked is True
    assert blocked.mode == "blocked"
    assert "experimental" in (blocked.blocker or "").lower()
    assert "not sent" in (blocked.blocker or "").lower()


def test_story_c_finds_shared_origin_and_contradiction_without_network(tmp_path):
    orchestrator = Orchestrator(tmp_path / "story.sqlite", retrieval=_offline_retrieval(tmp_path), post=_down)
    export = orchestrator.run_story_c()
    assert export.investigation.decision_source == "fallback"
    assert export.investigation.stop_reason == "unresolved_uncertainty"
    assert export.investigation.usage.network_calls == 0
    assert export.investigation.usage.llm_calls == 0
    assert export.investigation.usage.provider_calls == 0
    assert export.investigation.usage.search_calls == 1
    assert len(export.origin_clusters) == 1
    cluster = export.origin_clusters[0]
    assert cluster.origin_id == "LF-PR-2026-031"
    assert len(cluster.document_ids) == 4
    assert len(cluster.original_document_ids) == 1
    assert len(cluster.derivative_document_ids) == 3
    assert export.contradictions
    assert any(item.conflicting_object == "$480 million" and item.supported_object == "$400 million" for item in export.contradictions)
    raised = [rel for rel in export.relationships if rel.predicate == "raised_amount"]
    assert any(rel.object_name == "$480 million" and rel.status == "contradicted" for rel in raised)
    assert any(rel.object_name == "$400 million" and rel.status == "supported" for rel in raised)
    assert not any(rel.status == "supported" and "independent" in rel.predicate for rel in export.relationships)
    versions = {version.id: version for version in export.document_versions}
    assert export.evidence_spans
    for span in export.evidence_spans:
        version = versions[span.version_id]
        assert version.content[span.start : span.end] == span.text
    contradicted_ids = {rel.id for rel in export.relationships if rel.status == "contradicted"}
    contradicted_links = [link for link in export.evidence_links if link.relationship_id in contradicted_ids]
    assert contradicted_links
    assert all(link.quote_valid and link.semantic_status == "contradicted" for link in contradicted_links)
    assert len(export.checkpoints) >= 2
    resume_stats = orchestrator.resume(export.investigation.id)
    assert resume_stats["network_fetches"] == 0
    assert resume_stats["unchanged_versions"] == 4


def test_checkpoint_and_question_survive_reopen(tmp_path):
    path = tmp_path / "persist.sqlite"
    first = Orchestrator(path, retrieval=_offline_retrieval(tmp_path), post=_down)
    export = first.run_story_c()
    first.database.close()
    second = Orchestrator(path, retrieval=_offline_retrieval(tmp_path), post=_down)
    loaded = second.get(export.investigation.id)
    assert loaded.investigation.question == export.investigation.question
    assert len(loaded.checkpoints) >= 2
    assert loaded.checkpoints[0].state_json["question"] == export.investigation.question
    loaded.investigation.question = "a different question"
    with pytest.raises(ValueError):
        second.database.update_investigation(loaded.investigation, None)


def test_convergence_request_and_fallback(tmp_path):
    captured = {}

    def post(url, json, timeout):
        captured["url"] = url
        captured["json"] = json

        class Response:
            def raise_for_status(self):
                return None

            def json(self):
                return {
                    "stop": True,
                    "stop_reason": "low_expected_value",
                    "rationale": "controller says stop",
                    "decision_source": "fallback",
                }

        return Response()

    orchestrator = Orchestrator(
        tmp_path / "conv.sqlite",
        retrieval=_offline_retrieval(tmp_path),
        post=post,
        convergence_url="http://127.0.0.1:8000/api/convergence/evaluate",
    )
    export = orchestrator.run_story_c()
    body = ConvergenceEvaluateRequest.model_validate(captured["json"])
    assert body.original_question.startswith("Do three articles")
    assert body.budget.remaining_searches >= 0
    assert body.proposed_actions
    assert body.open_questions
    assert export.investigation.decision_source == "convergence"
    assert export.investigation.stop_reason == "low_expected_value"
    assert export.investigation.usage.search_calls == 0
    assert "controller says stop" in export.investigation.decision_rationale

    questions = [
        UnresolvedQuestion(id="q1", text="independent confirmation of the amount", importance=0.2, missing_evidence=0.2, kind="independence")
    ]
    low = fallback_decision(
        investigation_id="inv",
        questions=questions,
        actions=generate_actions(questions, []),
        budget=InvestigationBudget(max_searches=2, min_utility=0.9),
        followups_executed=0,
        error_type="ConnectError",
    )
    assert low.decision_source == "fallback"
    assert low.stop_reason == "low_expected_value"
    assert low.approved_action is None

    high_question = UnresolvedQuestion(
        id="q2",
        text="independent confirmation of the amount",
        importance=0.9,
        missing_evidence=1.0,
        kind="independence",
    )
    approved = fallback_decision(
        investigation_id="inv",
        questions=[high_question],
        actions=generate_actions([high_question], []),
        budget=InvestigationBudget(max_searches=2),
        followups_executed=0,
        error_type="ConnectError",
    )
    assert approved.decision_source == "fallback"
    assert approved.approved_action is not None
    stopped = fallback_decision(
        investigation_id="inv",
        questions=[high_question],
        actions=generate_actions([high_question], []),
        budget=InvestigationBudget(max_searches=2, searches_used=0),
        followups_executed=1,
        error_type="ConnectError",
    )
    assert stopped.stop is True
    assert stopped.approved_action is None
    assert stopped.decision_source == "fallback"
    parsed = decision_from_controller(
        {"action": InvestigationAction(id="act", query="q", reason="because", utility=0.5).model_dump(), "rationale": "go", "stop": False},
        "inv",
    )
    assert parsed.decision_source == "convergence"
    assert parsed.approved_action is not None
    request = ConvergenceEvaluateRequest(
        investigation_id="inv",
        original_question="question",
        open_questions=[high_question],
        proposed_actions=generate_actions([high_question], []),
        budget=InvestigationBudget(),
    )
    down = evaluate_controller(request, followups_executed=0, post=_down)
    assert down.decision_source == "fallback"
    assert "ConnectError" in down.rationale
