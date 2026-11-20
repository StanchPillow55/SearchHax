"""The checkpoint records the step latency stored on the investigation."""

from __future__ import annotations

from exploration.backend.orchestrator import STORY_A_QUESTION, Orchestrator
from exploration.backend.retrieval import RetrievalClient

PAGE = "NVIDIA has invested $2 billion in CoreWeave."


def test_checkpoint_records_the_step_latency(tmp_path, monkeypatch):
    monkeypatch.setenv("TELEM_API_KEY", "qa-dummy")
    monkeypatch.setattr("exploration.backend.orchestrator._elapsed_ms", lambda _started: 123)

    def search_fn(query, session_id):
        del query, session_id
        return {
            "session_id": "sess-latency",
            "interaction_id": "int-latency",
            "provider_runs": [
                {
                    "provider": "brave",
                    "results": [
                        {"url": "https://news.example/a", "title": "NVIDIA", "summary": PAGE, "provider": "brave"}
                    ],
                }
            ],
        }

    def fetch_fn(urls, session_id):
        del session_id
        return {"results": [{"url": urls[0], "content": PAGE, "status": "ok", "provider": "telem"}]}

    orchestrator = Orchestrator(
        tmp_path / "latency.sqlite",
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
    recorded = [item.state_json["usage"]["latency_ms"] for item in export.checkpoints]
    assert export.investigation.usage.latency_ms == 123
    assert recorded == [123], (recorded, export.investigation.usage.latency_ms)
