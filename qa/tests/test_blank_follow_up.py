"""A blank approved query does not consume a search."""

from __future__ import annotations

from exploration.backend.orchestrator import STORY_A_QUESTION, Orchestrator
from exploration.backend.retrieval import RetrievalClient

TEXT = "NVIDIA has invested $2 billion in CoreWeave."


def test_blank_approved_query_is_not_searched(tmp_path, monkeypatch):
    monkeypatch.setenv("TELEM_API_KEY", "qa-dummy")
    queries: list[str] = []

    def search_fn(query, session_id):
        del session_id
        queries.append(query)
        return {
            "session_id": "sess-blank",
            "interaction_id": f"int-{len(queries)}",
            "provider_runs": [
                {
                    "provider": "brave",
                    "results": [
                        {"url": "https://news.example/a", "title": "NVIDIA", "summary": TEXT, "provider": "brave"}
                    ],
                }
            ],
        }

    def fetch_fn(urls, session_id):
        del session_id
        return {"results": [{"url": urls[0], "content": TEXT, "status": "ok", "provider": "telem"}]}

    def blank_post(url, json, timeout=None):
        del url, timeout

        class Response:
            def raise_for_status(self):
                return None

            def json(self):
                return {
                    "investigation_id": json["investigation_id"],
                    "approved_action": {"id": "act-blank", "query": "   ", "reason": "blank", "utility": 0.9},
                    "stop": False,
                    "stop_reason": None,
                    "rationale": "approved a blank query",
                    "decision_source": "convergence",
                }

        return Response()

    client = RetrievalClient(
        cache_dir=tmp_path / "cache",
        dry_run=False,
        search_fn=search_fn,
        fetch_fn=fetch_fn,
        sleeper=lambda _seconds: None,
    )
    orchestrator = Orchestrator(tmp_path / "blank.sqlite", retrieval=client, post=blank_post)
    created = orchestrator.create(STORY_A_QUESTION, mode="web")
    orchestrator.step(created.id)
    second = orchestrator.step(created.id)
    assert queries == ["NVIDIA CoreWeave investment AI factories capacity 2026"], (
        queries,
        second.investigation.usage.search_calls,
        second.investigation.stop_reason,
    )
    assert second.investigation.usage.search_calls == 1
