"""A fetch whose canonical URL differs from the requested URL is still stored."""

from __future__ import annotations

from exploration.backend.orchestrator import STORY_A_QUESTION, Orchestrator
from exploration.backend.retrieval import RetrievalClient

PAGE = "NVIDIA has invested $2 billion in CoreWeave."


def test_fetch_canonical_url_still_stores_the_page(tmp_path, monkeypatch):
    monkeypatch.setenv("TELEM_API_KEY", "qa-dummy")

    def search_fn(query, session_id):
        del query, session_id
        return {
            "session_id": "sess-canon",
            "interaction_id": "int-canon",
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
                    "canonical_url": "https://news.example/final",
                    "content": PAGE,
                    "status": "ok",
                    "provider": "telem",
                }
            ]
        }

    orchestrator = Orchestrator(
        tmp_path / "canon.sqlite",
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
    stored = [version.content for version in export.document_versions]
    assert stored == [PAGE], (stored, export.investigation.usage.search_calls)
