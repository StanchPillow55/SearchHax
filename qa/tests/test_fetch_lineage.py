"""A fetch interaction stays on the investigation's session lineage."""

from __future__ import annotations

from telem.models import FetchResponse, FetchResult

from exploration.backend.orchestrator import STORY_A_QUESTION, Orchestrator
from exploration.backend.retrieval import RetrievalClient

TEXT = "NVIDIA has invested $2 billion in CoreWeave."


def test_fetch_interaction_is_recorded(tmp_path, monkeypatch):
    monkeypatch.setenv("TELEM_API_KEY", "qa-dummy")

    def search_fn(query, session_id):
        del query, session_id
        return {
            "session_id": "sess-search",
            "interaction_id": "int-search",
            "provider_runs": [
                {
                    "provider": "brave",
                    "results": [
                        {"url": "https://news.example/a", "title": "NVIDIA", "summary": TEXT, "provider": "brave"}
                    ],
                }
            ],
        }

    class Client:
        def fetch(self, urls, session=None):
            assert session == "sess-search", session
            assert urls == ["https://news.example/a"]
            return FetchResponse(
                results=[
                    FetchResult(
                        url="https://news.example/a",
                        content=TEXT,
                        status="ok",
                        provider="telem",
                    )
                ],
                session_id="sess-search",
                interaction_id="int-fetch",
                status="ok",
            )

        def close(self):
            return None

    monkeypatch.setattr("exploration.backend.retrieval._telem_client", lambda _timeout: Client())
    orchestrator = Orchestrator(
        tmp_path / "lineage.sqlite",
        retrieval=RetrievalClient(
            cache_dir=tmp_path / "cache",
            dry_run=False,
            search_fn=search_fn,
            sleeper=lambda _seconds: None,
        ),
    )
    created = orchestrator.create(STORY_A_QUESTION, mode="web")
    export = orchestrator.step(created.id)
    assert export.investigation.usage.interaction_ids == ["int-search", "int-fetch"], (
        export.investigation.usage.interaction_ids,
        export.investigation.usage.session_id,
    )
