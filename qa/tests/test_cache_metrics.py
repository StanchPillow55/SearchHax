"""A page served from the fetch cache counts as a cache hit."""

from __future__ import annotations

from exploration.backend.orchestrator import STORY_A_QUESTION, Orchestrator
from exploration.backend.retrieval import RetrievalClient

TEXT = "NVIDIA has invested $2 billion in CoreWeave."


def test_cached_fetch_increments_cache_hits(tmp_path, monkeypatch):
    """The second investigation reuses the page and records the cache hit."""
    monkeypatch.setenv("TELEM_API_KEY", "qa-dummy")
    calls = {"fetch": 0}

    def search_fn(query, session_id):
        del query, session_id
        return {
            "session_id": "sess-cache",
            "interaction_id": "int-cache",
            "provider_runs": [
                {
                    "provider": "brave",
                    "results": [
                        {
                            "url": "https://news.example/a",
                            "title": "NVIDIA",
                            "summary": TEXT,
                            "provider": "brave",
                        }
                    ],
                }
            ],
        }

    def fetch_fn(urls, session_id):
        del session_id
        calls["fetch"] += 1
        return {"results": [{"url": urls[0], "content": TEXT, "status": "ok", "provider": "telem"}]}

    cache = tmp_path / "cache"

    def run(name: str):
        orchestrator = Orchestrator(
            tmp_path / f"{name}.sqlite",
            retrieval=RetrievalClient(
                cache_dir=cache,
                dry_run=False,
                search_fn=search_fn,
                fetch_fn=fetch_fn,
                sleeper=lambda _seconds: None,
            ),
            post=lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("controller down")),
        )
        return orchestrator.step(orchestrator.create(STORY_A_QUESTION, mode="web").id)

    first = run("first")
    assert first.documents
    assert calls["fetch"] == 1
    second = run("second")
    assert len(second.documents) == 1
    assert calls["fetch"] == 1
    assert second.investigation.usage.cache_hits == 1
