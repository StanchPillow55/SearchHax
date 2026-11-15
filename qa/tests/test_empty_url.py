"""A search hit with no URL is not fetched and is not stored."""

from __future__ import annotations

from exploration.backend.orchestrator import STORY_A_QUESTION, Orchestrator
from exploration.backend.retrieval import RetrievalClient

TEXT = "NVIDIA has invested $2 billion in CoreWeave."


def test_empty_result_url_is_not_stored(tmp_path, monkeypatch):
    monkeypatch.setenv("TELEM_API_KEY", "qa-dummy")
    fetched: list[str] = []

    def search_fn(query, session_id):
        del query, session_id
        return {
            "session_id": "sess-empty",
            "interaction_id": "int-empty",
            "provider_runs": [
                {
                    "provider": "brave",
                    "results": [
                        {"url": "", "title": "blank", "summary": TEXT, "provider": "brave"},
                        {
                            "url": "https://news.example/a",
                            "title": "NVIDIA",
                            "summary": TEXT,
                            "provider": "brave",
                        },
                    ],
                }
            ],
        }

    def fetch_fn(urls, session_id):
        del session_id
        fetched.extend(urls)
        return {"results": [{"url": url, "content": TEXT, "status": "ok", "provider": "telem"} for url in urls]}

    orchestrator = Orchestrator(
        tmp_path / "empty.sqlite",
        retrieval=RetrievalClient(
            cache_dir=tmp_path / "cache",
            dry_run=False,
            search_fn=search_fn,
            fetch_fn=fetch_fn,
            sleeper=lambda _seconds: None,
        ),
    )
    export = orchestrator.step(orchestrator.create(STORY_A_QUESTION, mode="web").id)
    assert fetched == ["https://news.example/a"]
    assert [document.canonical_url for document in export.documents] == ["https://news.example/a"]
