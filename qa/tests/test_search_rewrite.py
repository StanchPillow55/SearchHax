"""A question that is not Story A is not rewritten into the CoreWeave query."""

from __future__ import annotations

from exploration.backend.orchestrator import Orchestrator
from exploration.backend.retrieval import RetrievalClient

QUESTION = (
    "What risks follow an NVIDIA investment if inference capacity is already "
    "sufficient for current demand and no new data-center buildout is planned?"
)
COREWEAVE_QUERY = "NVIDIA CoreWeave investment AI factories capacity 2026"


def test_unrelated_nvidia_question_is_not_rewritten_to_coreweave(tmp_path, monkeypatch):
    monkeypatch.setenv("TELEM_API_KEY", "qa-dummy")
    queries: list[str] = []

    def search_fn(query, session_id):
        del session_id
        queries.append(query)
        return {"session_id": "sess-rewrite", "interaction_id": "int-rewrite", "provider_runs": []}

    orchestrator = Orchestrator(
        tmp_path / "rewrite.sqlite",
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
    assert queries == [QUESTION], (queries, export.investigation.question)
    assert COREWEAVE_QUERY not in queries
    assert export.investigation.question == QUESTION
