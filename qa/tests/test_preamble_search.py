"""A long question is not searched as only the sentence before the question."""

from __future__ import annotations

from exploration.backend.orchestrator import Orchestrator
from exploration.backend.retrieval import RetrievalClient

QUESTION = (
    "Please read the following background about market structure, supplier concentration, "
    "and prior reporting before you answer the actual question. "
    "What share of HBM supply did Samsung book for 2027?"
)


def test_long_question_keeps_the_sentence_after_the_preamble(tmp_path, monkeypatch):
    assert len(QUESTION) > 180, len(QUESTION)
    monkeypatch.setenv("TELEM_API_KEY", "qa-dummy")
    queries: list[str] = []

    def search_fn(query, session_id):
        del session_id
        queries.append(query)
        return {"session_id": "sess-preamble", "interaction_id": "int-preamble", "provider_runs": []}

    orchestrator = Orchestrator(
        tmp_path / "preamble.sqlite",
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
    assert queries and "Samsung" in queries[0], (queries, export.investigation.usage.search_calls)
    assert export.investigation.question == QUESTION
