"""Provider outages and the hard search cap, exercised through the investigation loop.

No live provider call is made.
"""

from __future__ import annotations

from exploration.backend.orchestrator import STORY_A_QUESTION, STORY_C_QUESTION, Orchestrator
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


def test_web_path_keeps_story_c_wire_as_one_origin_and_one_amount(tmp_path, monkeypatch):
    """The same wire fetched through search is one origin, and the derivative amount is not supported."""
    monkeypatch.setenv("TELEM_API_KEY", "qa-dummy")
    original = (
        "FOR IMMEDIATE RELEASE\n"
        "Lumenarc Dynamics raised $400 million Series D. Wire LF-PR-2026-031.\n"
        "https://lumenarc.example/press/series-d"
    )
    copy = (
        "VoltStreet reports Lumenarc Dynamics raised $480 million Series D, "
        "citing wire LF-PR-2026-031 and https://lumenarc.example/press/series-d."
    )
    pages = {
        "https://lumenarc.example/press/series-d": original,
        "https://voltstreet.example/lumenarc": copy,
    }

    def search_fn(query, session_id):
        del query, session_id
        return {
            "session_id": "sess-wire",
            "interaction_id": "int-wire",
            "provider_runs": [
                {
                    "provider": "brave",
                    "results": [
                        {"url": url, "title": url, "summary": text[:140], "provider": "brave"}
                        for url, text in pages.items()
                    ],
                }
            ],
        }

    def fetch_fn(urls, session_id):
        del session_id
        return {"results": [{"url": url, "content": pages[url], "status": "ok", "provider": "telem"} for url in urls]}

    orchestrator = Orchestrator(
        tmp_path / "wire.sqlite",
        retrieval=_client(tmp_path, search_fn, fetch_fn),
        post=lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("controller down")),
    )
    investigation = orchestrator.create(STORY_C_QUESTION, mode="web")
    export = orchestrator.step(investigation.id)
    cluster = next((item for item in export.origin_clusters if item.origin_id == "LF-PR-2026-031"), None)
    assert cluster is not None and len(cluster.document_ids) >= 2
    amounts = [rel for rel in export.relationships if rel.predicate == "raised_amount"]
    assert any(rel.object_name == "$400 million" and rel.status == "supported" for rel in amounts)
    assert not any(rel.object_name == "$480 million" and rel.status == "supported" for rel in amounts)
    assert export.contradictions


def test_failed_fetch_body_is_not_stored_as_evidence(tmp_path, monkeypatch):
    """A fetch that reports an error is not a source, even when the body contains the sentence."""
    monkeypatch.setenv("TELEM_API_KEY", "qa-dummy")
    body = "404 Not Found\nThe rumor page includes this leftover line: NVIDIA has invested $2 billion in CoreWeave."

    def search_fn(query, session_id):
        del query, session_id
        return {
            "session_id": "sess-404",
            "interaction_id": "int-404",
            "provider_runs": [
                {
                    "provider": "brave",
                    "results": [
                        {
                            "url": "https://news.example/missing",
                            "title": "Missing",
                            "summary": "NVIDIA CoreWeave",
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
                    "content": body,
                    "status": "error",
                    "error": "HTTP 404",
                    "provider": "telem",
                }
            ]
        }

    orchestrator = Orchestrator(
        tmp_path / "missing.sqlite",
        retrieval=_client(tmp_path, search_fn, fetch_fn),
        post=lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("controller down")),
    )
    investigation = orchestrator.create(STORY_A_QUESTION, mode="web")
    export = orchestrator.step(investigation.id)
    supported = [rel for rel in export.relationships if rel.status == "supported"]
    assert supported == []
    assert export.documents == []


def test_failed_fetch_is_not_replayed_from_cache(tmp_path, monkeypatch):
    """A later investigation must not reuse a cached error body as the page."""
    monkeypatch.setenv("TELEM_API_KEY", "qa-dummy")
    body = "404 Not Found\nNVIDIA has invested $2 billion in CoreWeave."
    good = "NVIDIA has invested $2 billion in CoreWeave."
    calls = {"n": 0}

    def search_fn(query, session_id):
        del query, session_id
        return {
            "session_id": "sess-404",
            "interaction_id": "int-404",
            "provider_runs": [
                {
                    "provider": "brave",
                    "results": [
                        {
                            "url": "https://news.example/missing",
                            "title": "Missing",
                            "summary": "NVIDIA CoreWeave",
                            "provider": "brave",
                        }
                    ],
                }
            ],
        }

    def fetch_bad(urls, session_id):
        del urls, session_id
        return {
            "results": [
                {
                    "url": "https://news.example/missing",
                    "content": body,
                    "status": "error",
                    "error": "HTTP 404",
                    "provider": "telem",
                }
            ]
        }

    def fetch_good(urls, session_id):
        del session_id
        calls["n"] += 1
        return {"results": [{"url": urls[0], "content": good, "status": "ok", "provider": "telem"}]}

    cache = tmp_path / "cache"
    first = Orchestrator(
        tmp_path / "first.sqlite",
        retrieval=RetrievalClient(cache_dir=cache, dry_run=False, search_fn=search_fn, fetch_fn=fetch_bad, sleeper=lambda _seconds: None),
        post=lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("controller down")),
    )
    first.step(first.create(STORY_A_QUESTION, mode="web").id)
    second = Orchestrator(
        tmp_path / "second.sqlite",
        retrieval=RetrievalClient(cache_dir=cache, dry_run=False, search_fn=search_fn, fetch_fn=fetch_good, sleeper=lambda _seconds: None),
        post=lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("controller down")),
    )
    export = second.step(second.create(STORY_A_QUESTION, mode="web").id)
    assert calls["n"] == 1
    assert export.document_versions
    assert export.document_versions[0].content == good
    for span in export.evidence_spans:
        version = next(item for item in export.document_versions if item.id == span.version_id)
        assert version.content[span.start : span.end] == span.text
        assert not span.text.startswith("404")


def test_empty_failed_fetch_is_recorded(tmp_path, monkeypatch):
    """A fetch that returns an error and no body does not look like a run still in progress."""
    monkeypatch.setenv("TELEM_API_KEY", "qa-dummy")

    def search_fn(query, session_id):
        del query, session_id
        return {
            "session_id": "sess-empty",
            "interaction_id": "int-empty",
            "provider_runs": [
                {
                    "provider": "brave",
                    "results": [
                        {
                            "url": "https://news.example/missing",
                            "title": "Missing",
                            "summary": "NVIDIA has invested $2 billion in CoreWeave.",
                            "provider": "brave",
                        }
                    ],
                }
            ],
        }

    def fetch_fn(urls, session_id):
        del session_id
        return {"results": [{"url": urls[0], "content": "", "status": "error", "error": "HTTP 404", "provider": "telem"}]}

    orchestrator = Orchestrator(
        tmp_path / "empty.sqlite",
        retrieval=_client(tmp_path, search_fn, fetch_fn),
        post=lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("controller down")),
    )
    export = orchestrator.step(orchestrator.create(STORY_A_QUESTION, mode="web").id)
    assert export.documents == []
    assert export.relationships == []
    visible = " ".join(
        part
        for part in (
            export.investigation.blocker,
            export.investigation.stop_reason,
            export.investigation.decision_rationale,
        )
        if part
    ).lower()
    assert export.investigation.status == "stopped"
    assert any(token in visible for token in ("404", "error", "unavailable"))


def test_search_exception_is_recorded_instead_of_escaping(tmp_path, monkeypatch):
    """A raised provider error is stored on the investigation after the bounded retries."""
    monkeypatch.setenv("TELEM_API_KEY", "qa-dummy")

    class Unavailable(Exception):
        status_code = 503

    calls = {"search": 0, "fetch": 0}

    def search_fn(query, session_id):
        del query, session_id
        calls["search"] += 1
        raise Unavailable("provider unavailable")

    def fetch_fn(urls, session_id):
        del urls, session_id
        calls["fetch"] += 1
        raise AssertionError("fetch ran after a search exception")

    orchestrator = Orchestrator(
        tmp_path / "raise.sqlite",
        retrieval=_client(tmp_path, search_fn, fetch_fn),
        post=lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("controller down")),
    )
    investigation = orchestrator.create(STORY_A_QUESTION, mode="web")
    export = orchestrator.step(investigation.id)
    visible = " ".join(
        part
        for part in (
            export.investigation.blocker,
            export.investigation.stop_reason,
            export.investigation.decision_rationale,
        )
        if part
    ).lower()
    assert export.investigation.status in {"stopped", "blocked"}
    assert any(token in visible for token in ("503", "unavailable", "error"))
    assert export.documents == []
    assert export.relationships == []
    assert calls["fetch"] == 0
    assert calls["search"] <= 3
