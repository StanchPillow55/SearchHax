"""A controller that approves nothing does not leave the investigation running."""

from __future__ import annotations

from exploration.backend.orchestrator import STORY_A_QUESTION, Orchestrator
from exploration.backend.retrieval import RetrievalClient

TEXT = "NVIDIA has invested $2 billion in CoreWeave."


def test_no_action_and_no_stop_does_not_stay_running(tmp_path, monkeypatch):
    monkeypatch.setenv("TELEM_API_KEY", "qa-dummy")

    def search_fn(query, session_id):
        del query, session_id
        return {
            "session_id": "sess-idle",
            "interaction_id": "int-idle",
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

    def idle_post(url, json, timeout=None):
        del url, timeout

        class Response:
            def raise_for_status(self):
                return None

            def json(self):
                return {
                    "investigation_id": json["investigation_id"],
                    "approved_action": None,
                    "stop": False,
                    "stop_reason": None,
                    "rationale": "no action this round",
                    "decision_source": "convergence",
                }

        return Response()

    orchestrator = Orchestrator(
        tmp_path / "idle.sqlite",
        retrieval=RetrievalClient(
            cache_dir=tmp_path / "cache",
            dry_run=False,
            search_fn=search_fn,
            fetch_fn=fetch_fn,
            sleeper=lambda _seconds: None,
        ),
        post=idle_post,
    )
    created = orchestrator.create(STORY_A_QUESTION, mode="web")
    orchestrator.step(created.id)
    second = orchestrator.step(created.id)
    assert second.investigation.status == "stopped", (
        second.investigation.status,
        second.investigation.stop_reason,
        second.investigation.usage.search_calls,
    )
    assert second.investigation.usage.search_calls == 1
