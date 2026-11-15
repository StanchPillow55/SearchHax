"""A synthesized answer may cite only the supplied evidence."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from exploration.backend.answer import compose_answer
from exploration.backend.main import create_app
from exploration.backend.orchestrator import STORY_A_QUESTION, Orchestrator
from exploration.backend.retrieval import RetrievalClient
from shared.contracts import (
    Document,
    DocumentVersion,
    EvidenceLink,
    EvidenceSpan,
    ExplorationExport,
    Investigation,
    InvestigationBudget,
    Relationship,
)

QUOTE = "NVIDIA has invested $2 billion in CoreWeave."
NOW = datetime(2026, 11, 14, 20, 0, tzinfo=timezone.utc)


class _AnswerClient:
    def __init__(self, *args, **kwargs):
        del args, kwargs
        self.configured = True
        self.model = "qa-answer"
        self.calls = 0

    def complete_text(self, system, user):
        del system, user
        self.calls += 1
        return (
            "NVIDIA invested $2 billion [S99]. See https://evil.example/fake [S1].",
            {"total_tokens": 3},
        )


def _export() -> ExplorationExport:
    return ExplorationExport(
        investigation=Investigation(
            id="inv-answer",
            question=STORY_A_QUESTION,
            budget=InvestigationBudget(),
            status="stopped",
            created_at=NOW,
            updated_at=NOW,
        ),
        documents=[Document(id="doc-1", canonical_url="https://news.example/a", title="NVIDIA")],
        document_versions=[
            DocumentVersion(
                id="ver-1",
                document_id="doc-1",
                content_hash="hash-1",
                fetched_at=NOW,
                content=QUOTE,
            )
        ],
        evidence_spans=[
            EvidenceSpan(
                id="span-1",
                version_id="ver-1",
                document_id="doc-1",
                text=QUOTE,
                start=0,
                end=len(QUOTE),
                content_hash="hash-1",
                quote_valid=True,
            )
        ],
        relationships=[
            Relationship(
                id="rel-1",
                subject_id="ent-nvidia",
                predicate="invested_in",
                object_id="ent-coreweave",
                status="supported",
                document_id="doc-1",
                subject_name="NVIDIA",
                object_name="CoreWeave",
                evidence_link_ids=["link-1"],
            )
        ],
        evidence_links=[
            EvidenceLink(
                id="link-1",
                claim_id="claim-1",
                relationship_id="rel-1",
                evidence_span_id="span-1",
                stance="supports",
                quote_valid=True,
                semantic_status="supported",
            )
        ],
    )


def test_invented_marker_and_url_are_not_published():
    answer = compose_answer(_export(), client=_AnswerClient())
    assert "[S99]" not in answer.markdown, answer.markdown
    assert "evil.example" not in answer.markdown, answer.markdown
    assert answer.cited_markers == ["S1"], answer.cited_markers


def test_missing_answer_key_does_not_invent_prose(monkeypatch):
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    answer = compose_answer(_export())
    assert answer.blocked is True
    assert answer.markdown == ""
    assert answer.blocker and "not generated" in answer.blocker


def test_answer_call_stops_when_the_llm_budget_is_spent(tmp_path, monkeypatch):
    monkeypatch.setenv("TELEM_API_KEY", "qa-dummy")
    calls: list[str] = []

    class Counting(_AnswerClient):
        def complete_text(self, system, user):
            del system
            calls.append(user)
            return ("NVIDIA has invested $2 billion in CoreWeave [S1].", {"total_tokens": 4})

    monkeypatch.setattr("exploration.backend.answer.OpenAICompatibleClient", Counting)

    def search_fn(query, session_id):
        del query, session_id
        return {
            "session_id": "sess-answer",
            "interaction_id": "int-answer",
            "provider_runs": [
                {
                    "provider": "brave",
                    "results": [
                        {"url": "https://news.example/a", "title": "NVIDIA", "summary": QUOTE, "provider": "brave"}
                    ],
                }
            ],
        }

    def fetch_fn(urls, session_id):
        del session_id
        return {"results": [{"url": urls[0], "content": QUOTE, "status": "ok", "provider": "telem"}]}

    db = tmp_path / "answer.sqlite"
    orchestrator = Orchestrator(
        db,
        retrieval=RetrievalClient(
            cache_dir=tmp_path / "cache",
            dry_run=False,
            search_fn=search_fn,
            fetch_fn=fetch_fn,
            sleeper=lambda _seconds: None,
        ),
    )
    created = orchestrator.create(STORY_A_QUESTION, mode="web")
    orchestrator.step(created.id)
    stored = orchestrator.get(created.id)
    stored.investigation.budget.llm_calls_used = stored.investigation.budget.max_llm_calls
    stored.investigation.usage.llm_calls = stored.investigation.budget.max_llm_calls
    orchestrator.database.update_investigation(stored.investigation, stored.decision)

    client = TestClient(create_app(db))
    answered = client.post(f"/api/exploration/investigations/{created.id}/answer")
    assert answered.status_code == 200, answered.text
    body = answered.json()
    assert calls == [], (len(calls), body["answer"]["blocked"], body["investigation"]["usage"]["llm_calls"])
    assert body["answer"]["blocked"] is True
    assert body["investigation"]["usage"]["llm_calls"] == stored.investigation.budget.max_llm_calls


def test_failed_answer_regeneration_keeps_the_stored_answer(tmp_path, monkeypatch):
    monkeypatch.setenv("TELEM_API_KEY", "qa-dummy")
    calls = {"n": 0}

    class Flip:
        def __init__(self, *args, **kwargs):
            del args, kwargs
            self.configured = True
            self.model = "qa-answer"

        def complete_text(self, system, user):
            del system, user
            calls["n"] += 1
            if calls["n"] == 1:
                return ("NVIDIA has invested $2 billion in CoreWeave [S1].", {"total_tokens": 4})
            raise RuntimeError("answer backend down")

    monkeypatch.setattr("exploration.backend.answer.OpenAICompatibleClient", Flip)

    def search_fn(query, session_id):
        del query, session_id
        return {
            "session_id": "sess-keep",
            "interaction_id": "int-keep",
            "provider_runs": [
                {
                    "provider": "brave",
                    "results": [
                        {"url": "https://news.example/a", "title": "NVIDIA", "summary": QUOTE, "provider": "brave"}
                    ],
                }
            ],
        }

    def fetch_fn(urls, session_id):
        del session_id
        return {"results": [{"url": urls[0], "content": QUOTE, "status": "ok", "provider": "telem"}]}

    db = tmp_path / "keep.sqlite"
    orchestrator = Orchestrator(
        db,
        retrieval=RetrievalClient(
            cache_dir=tmp_path / "cache",
            dry_run=False,
            search_fn=search_fn,
            fetch_fn=fetch_fn,
            sleeper=lambda _seconds: None,
        ),
    )
    created = orchestrator.create(STORY_A_QUESTION, mode="web")
    orchestrator.step(created.id)
    client = TestClient(create_app(db))
    path = f"/api/exploration/investigations/{created.id}/answer"
    first = client.post(path)
    assert first.status_code == 200, first.text
    assert "NVIDIA has invested $2 billion in CoreWeave [S1]." in first.json()["answer"]["markdown"]
    second = client.post(path)
    assert second.status_code == 200, second.text
    stored = second.json()["answer"]
    assert stored["blocked"] is False, (stored["blocked"], stored["markdown"], stored["blocker"])
    assert "NVIDIA has invested $2 billion in CoreWeave [S1]." in stored["markdown"], stored["markdown"]
