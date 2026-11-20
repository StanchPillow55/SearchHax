"""The controller ranks the fetched page, not the search snippet."""

from __future__ import annotations

from exploration.backend.orchestrator import STORY_A_QUESTION, Orchestrator
from exploration.backend.retrieval import RetrievalClient

PAGE = "NVIDIA has invested $2 billion in CoreWeave. The buildout emphasizes advanced packaging."


def test_fetched_page_is_what_the_controller_ranks(tmp_path, monkeypatch):
    monkeypatch.setenv("TELEM_API_KEY", "qa-dummy")
    seen: list[str] = []

    def search_fn(query, session_id):
        del query, session_id
        return {
            "session_id": "sess-page",
            "interaction_id": "int-page",
            "provider_runs": [
                {
                    "provider": "brave",
                    "results": [
                        {
                            "url": "https://news.example/a",
                            "title": "Brief",
                            "summary": "Brief.",
                            "provider": "brave",
                        }
                    ],
                }
            ],
        }

    def fetch_fn(urls, session_id):
        del session_id
        return {"results": [{"url": urls[0], "content": PAGE, "status": "ok", "provider": "telem"}]}

    def record_post(url, json, timeout=None):
        del url, timeout
        seen.extend(candidate.get("snippet") or "" for candidate in json["candidates"])

        class Response:
            def raise_for_status(self):
                return None

            def json(self):
                return {
                    "investigation_id": json["investigation_id"],
                    "approved_action": None,
                    "stop": True,
                    "stop_reason": "evidence_sufficient",
                    "rationale": "recorded the candidate text",
                    "decision_source": "convergence",
                }

        return Response()

    orchestrator = Orchestrator(
        tmp_path / "page.sqlite",
        retrieval=RetrievalClient(
            cache_dir=tmp_path / "cache",
            dry_run=False,
            search_fn=search_fn,
            fetch_fn=fetch_fn,
            sleeper=lambda _seconds: None,
        ),
        post=record_post,
    )
    created = orchestrator.create(STORY_A_QUESTION, mode="web")
    first = orchestrator.step(created.id)
    assert first.document_versions[0].content == PAGE
    orchestrator.step(created.id)
    assert seen and "CoreWeave" in seen[0], seen
