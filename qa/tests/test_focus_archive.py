"""An archived page does not cancel an open follow-up that is above the utility floor."""

from __future__ import annotations

from shared.contracts import ResearchProfile

from exploration.backend.focus_bridge import focus_post
from exploration.backend.orchestrator import STORY_A_QUESTION, Orchestrator
from exploration.backend.retrieval import RetrievalClient

TEXT = "NVIDIA has invested $2 billion in CoreWeave. The buildout emphasizes advanced packaging."


def test_archived_page_does_not_drop_the_open_follow_up(tmp_path, monkeypatch):
    monkeypatch.setenv("TELEM_API_KEY", "qa-dummy")

    def search_fn(query, session_id):
        del query, session_id
        return {
            "session_id": "sess-archive",
            "interaction_id": "int-archive",
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

    orchestrator = Orchestrator(
        tmp_path / "archive.sqlite",
        retrieval=RetrievalClient(
            cache_dir=tmp_path / "cache",
            dry_run=False,
            search_fn=search_fn,
            fetch_fn=fetch_fn,
            sleeper=lambda _seconds: None,
        ),
        post=focus_post,
    )
    created = orchestrator.create(
        STORY_A_QUESTION,
        mode="web",
        profile=ResearchProfile(
            id="profile-qa",
            interests=["advanced packaging"],
            unresolved_interests=["advanced packaging"],
        ),
    )
    orchestrator.step(created.id)
    second = orchestrator.step(created.id)
    pending = [(round(action.utility, 2), action.query) for action in second.actions]
    assert second.investigation.usage.search_calls == 2, (
        second.investigation.stop_reason,
        second.investigation.usage.search_calls,
        pending,
    )
