"""Provider outages and the hard search cap, exercised through the investigation loop.

No live provider call is made.
"""

from __future__ import annotations

from exploration.backend.orchestrator import STORY_A_QUESTION, Orchestrator
from exploration.backend.retrieval import RetrievalClient

PAGE = "NVIDIA has invested $2 billion in CoreWeave."


def _client(tmp_path, search_fn, fetch_fn) -> RetrievalClient:
    return RetrievalClient(
        cache_dir=tmp_path / "cache",
        dry_run=False,
        search_fn=search_fn,
        fetch_fn=fetch_fn,
        sleeper=lambda _seconds: None,
    )


def test_provider_outage_is_recorded_and_the_investigation_stops(tmp_path, monkeypatch):
    """A search whose providers fail must not look like a run still in progress."""
    monkeypatch.setenv("TELEM_API_KEY", "qa-dummy")

    def search_fn(query, session_id):
        del query, session_id
        return {
            "session_id": "sess-outage",
            "interaction_id": "int-outage",
            "by_provider": [
                {"provider": "brave", "status": 503, "error": "unavailable", "results": []},
                {"provider": "tavily", "status": 429, "error": "rate limit", "results": []},
            ],
        }

    def fetch_fn(urls, session_id):
        del session_id
        raise AssertionError(f"fetch ran for {urls}")

    orchestrator = Orchestrator(
        tmp_path / "outage.sqlite",
        retrieval=_client(tmp_path, search_fn, fetch_fn),
        post=lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("controller not called")),
    )
    investigation = orchestrator.create("battery degradation resale value", mode="web")
    export = orchestrator.step(investigation.id)
    recorded = " ".join(
        part
        for part in (
            export.investigation.blocker,
            export.investigation.decision_rationale,
            export.investigation.stop_reason,
        )
        if part
    ).lower()
    assert export.relationships == []
    assert export.documents == []
    assert export.investigation.status == "stopped"
    assert "503" in recorded or "429" in recorded or "unavailable" in recorded or "rate limit" in recorded


def test_third_distinct_search_stops_on_budget(tmp_path, monkeypatch):
    monkeypatch.setenv("TELEM_API_KEY", "qa-dummy")
    calls = {"n": 0}

    def search_fn(query, session_id):
        del session_id
        calls["n"] += 1
        return {
            "session_id": "sess-budget",
            "interaction_id": str(calls["n"]),
            "provider_runs": [
                {
                    "provider": "brave",
                    "results": [
                        {
                            "url": f"https://example.com/page-{calls['n']}",
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
        return {"results": [{"url": urls[0], "content": PAGE, "status": "ok", "provider": "telem"}]}

    def post(url, json, timeout):  # noqa: A002
        del url, json, timeout
        step = calls["n"]

        class Response:
            def raise_for_status(self):
                return None

            def json(self):
                return {
                    "stop": False,
                    "rationale": "approve another search",
                    "approved_action": {
                        "id": f"act-{step}",
                        "query": f"downstream demand follow up {step}",
                        "reason": "controller wants another search",
                        "utility": 0.9,
                    },
                }

        return Response()

    orchestrator = Orchestrator(
        tmp_path / "budget.sqlite",
        retrieval=_client(tmp_path, search_fn, fetch_fn),
        post=post,
    )
    investigation = orchestrator.create(STORY_A_QUESTION, mode="web")
    first = orchestrator.step(investigation.id)
    second = orchestrator.step(investigation.id)
    third = orchestrator.step(investigation.id)
    assert calls["n"] == 2
    assert first.investigation.budget.searches_used == 1
    assert second.investigation.status == "stopped"
    assert second.investigation.stop_reason == "budget_exhausted"
    assert third.investigation.status == "stopped"
    assert third.investigation.budget.searches_used == 2
    assert third.relationships
    for span in third.evidence_spans:
        version = next(item for item in third.document_versions if item.id == span.version_id)
        assert version.content[span.start : span.end] == span.text


def test_web_path_does_not_accept_two_amounts_as_supported(tmp_path, monkeypatch):
    """Two exact but disagreeing investment sentences cannot both stay supported."""
    monkeypatch.setenv("TELEM_API_KEY", "qa-dummy")
    pages = {
        "https://news.example/two": "NVIDIA has invested $2 billion in CoreWeave.",
        "https://news.example/five": "NVIDIA has invested $5 billion in CoreWeave.",
    }

    def search_fn(query, session_id):
        del query, session_id
        return {
            "session_id": "sess-conflict",
            "interaction_id": "int-conflict",
            "provider_runs": [
                {
                    "provider": "brave",
                    "results": [
                        {"url": url, "title": "NVIDIA", "summary": text, "provider": "brave"}
                        for url, text in pages.items()
                    ],
                }
            ],
        }

    def fetch_fn(urls, session_id):
        del session_id
        return {
            "results": [
                {"url": url, "content": pages[url], "status": "ok", "provider": "telem"} for url in urls
            ]
        }

    orchestrator = Orchestrator(
        tmp_path / "conflict.sqlite",
        retrieval=_client(tmp_path, search_fn, fetch_fn),
        post=lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("controller not called")),
    )
    investigation = orchestrator.create(STORY_A_QUESTION, mode="web")
    export = orchestrator.step(investigation.id)
    amounts = [rel for rel in export.relationships if rel.predicate == "invested_amount"]
    supported = [rel for rel in amounts if rel.status == "supported"]
    assert len(amounts) == 2
    for rel in amounts:
        link = next(item for item in export.evidence_links if item.id == rel.evidence_link_ids[0])
        span = next(item for item in export.evidence_spans if item.id == link.evidence_span_id)
        version = next(item for item in export.document_versions if item.id == span.version_id)
        assert version.content[span.start : span.end] == span.text
    assert export.contradictions or len(supported) < 2
    assert not (len(supported) == 2 and not export.contradictions)


def test_negated_investment_sentence_is_not_supported(tmp_path, monkeypatch):
    """A denial that contains the investment wording is not a supported edge."""
    monkeypatch.setenv("TELEM_API_KEY", "qa-dummy")
    text = "The rumor that NVIDIA has invested $2 billion in CoreWeave is unconfirmed and is not in the filing."

    def search_fn(query, session_id):
        del query, session_id
        return {
            "session_id": "sess-rumor",
            "interaction_id": "int-rumor",
            "provider_runs": [
                {
                    "provider": "brave",
                    "results": [
                        {
                            "url": "https://news.example/rumor",
                            "title": "Rumor",
                            "summary": text,
                            "provider": "brave",
                        }
                    ],
                }
            ],
        }

    def fetch_fn(urls, session_id):
        del session_id
        return {"results": [{"url": urls[0], "content": text, "status": "ok", "provider": "telem"}]}

    orchestrator = Orchestrator(
        tmp_path / "rumor.sqlite",
        retrieval=_client(tmp_path, search_fn, fetch_fn),
        post=lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("controller not called")),
    )
    investigation = orchestrator.create(STORY_A_QUESTION, mode="web")
    export = orchestrator.step(investigation.id)
    supported = [rel for rel in export.relationships if rel.status == "supported"]
    assert supported == []
    for span in export.evidence_spans:
        version = next(item for item in export.document_versions if item.id == span.version_id)
        assert version.content[span.start : span.end] == span.text
        assert "unconfirmed" in version.content[max(0, span.start - 80) : span.end + 80] or span.text == ""


def test_causal_demand_sentence_does_not_close_the_gap(tmp_path, monkeypatch):
    """Mentioning customer demand in a causal sentence is not evidence that demand is known."""
    monkeypatch.setenv("TELEM_API_KEY", "qa-dummy")
    text = (
        "NVIDIA has invested $2 billion in CoreWeave. "
        "That investment caused customer demand for AI factories to rise."
    )

    def search_fn(query, session_id):
        del query, session_id
        return {
            "session_id": "sess-cause",
            "interaction_id": "int-cause",
            "provider_runs": [
                {
                    "provider": "brave",
                    "results": [
                        {
                            "url": "https://news.example/cause",
                            "title": "Cause",
                            "summary": text,
                            "provider": "brave",
                        }
                    ],
                }
            ],
        }

    def fetch_fn(urls, session_id):
        del session_id
        return {"results": [{"url": urls[0], "content": text, "status": "ok", "provider": "telem"}]}

    orchestrator = Orchestrator(
        tmp_path / "cause.sqlite",
        retrieval=_client(tmp_path, search_fn, fetch_fn),
        post=lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("controller down")),
    )
    investigation = orchestrator.create(STORY_A_QUESTION, mode="web")
    export = orchestrator.step(investigation.id)
    extra = [rel for rel in export.relationships if rel.predicate not in {"invested_in", "invested_amount"}]
    assert all(rel.status != "supported" for rel in extra)
    demand_open = any("demand" in question.text.lower() for question in export.unresolved_questions)
    demand_hypothesis = any(rel.status in {"hypothesis", "insufficient"} and "demand" in f"{rel.predicate} {rel.object_name} {rel.notes}".lower() for rel in extra)
    assert demand_open or demand_hypothesis
