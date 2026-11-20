"""A long question does not turn into an empty search."""

from __future__ import annotations

from exploration.backend.orchestrator import Orchestrator
from exploration.backend.retrieval import RetrievalClient

QUESTION = "." + ("capacity planning " * 12)


def test_long_question_does_not_search_an_empty_query(tmp_path, monkeypatch):
    monkeypatch.setenv("TELEM_API_KEY", "qa-dummy")
    queries: list[str] = []

    def search_fn(query, session_id):
        del session_id
        queries.append(query)
        return {"session_id": "sess-empty-q", "interaction_id": "int-empty-q", "provider_runs": []}

    orchestrator = Orchestrator(
        tmp_path / "empty-query.sqlite",
        retrieval=RetrievalClient(
            cache_dir=tmp_path / "cache",
            dry_run=False,
            search_fn=search_fn,
            fetch_fn=lambda urls, session_id: {"results": []},
            sleeper=lambda _seconds: None,
        ),
    )
    created = orchestrator.create(QUESTION, mode="web")
    export = orchestrator.step(created.id)
    assert queries == [], (queries, export.investigation.usage.search_calls)
    assert export.investigation.question == QUESTION
    assert export.investigation.usage.search_calls == 0
