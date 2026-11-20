"""An empty fetched body does not spend a URL slot."""

from __future__ import annotations

from exploration.backend.orchestrator import STORY_A_QUESTION, Orchestrator
from exploration.backend.retrieval import RetrievalClient


def test_empty_ok_fetch_does_not_spend_a_url_slot(tmp_path, monkeypatch):
    monkeypatch.setenv("TELEM_API_KEY", "qa-dummy")

    def search_fn(query, session_id):
        del query, session_id
        return {
            "session_id": "sess-empty",
            "interaction_id": "int-empty",
            "provider_runs": [
                {
                    "provider": "brave",
                    "results": [
                        {
                            "url": "https://news.example/a",
                            "title": "NVIDIA",
                            "summary": "NVIDIA CoreWeave",
                            "provider": "brave",
                        }
                    ],
                }
            ],
        }

    def fetch_fn(urls, session_id):
        del session_id
        return {"results": [{"url": urls[0], "content": "", "status": "ok", "provider": "telem"}]}

    orchestrator = Orchestrator(
        tmp_path / "empty-ok.sqlite",
        retrieval=RetrievalClient(
            cache_dir=tmp_path / "cache",
            dry_run=False,
            search_fn=search_fn,
            fetch_fn=fetch_fn,
            sleeper=lambda _seconds: None,
        ),
    )
    created = orchestrator.create(STORY_A_QUESTION, mode="web")
    export = orchestrator.step(created.id)
    assert export.document_versions == []
    assert export.investigation.budget.urls_fetched == 0, (
        export.investigation.budget.urls_fetched,
        export.investigation.usage.fetch_calls,
    )
