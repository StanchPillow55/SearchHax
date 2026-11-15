"""A publish date returned by the fetch is stored on the page."""

from __future__ import annotations

from exploration.backend.orchestrator import STORY_A_QUESTION, Orchestrator
from exploration.backend.retrieval import RetrievalClient

PAGE = "NVIDIA has invested $2 billion in CoreWeave."


def test_fetch_publish_date_is_stored(tmp_path, monkeypatch):
    monkeypatch.setenv("TELEM_API_KEY", "qa-dummy")

    def search_fn(query, session_id):
        del query, session_id
        return {
            "session_id": "sess-date",
            "interaction_id": "int-date",
            "provider_runs": [
                {
                    "provider": "brave",
                    "results": [
                        {
                            "url": "https://news.example/a",
                            "title": "NVIDIA",
                            "summary": PAGE,
                            "provider": "brave",
                        }
                    ],
                }
            ],
        }

    def fetch_fn(urls, session_id):
        del session_id
        return {
            "results": [
                {
                    "url": urls[0],
                    "content": PAGE,
                    "status": "ok",
                    "provider": "telem",
                    "publish_date": "2026-11-01",
                }
            ]
        }

    orchestrator = Orchestrator(
        tmp_path / "date.sqlite",
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
    dates = [version.publish_date for version in export.document_versions]
    assert dates == ["2026-11-01"], dates
