import pytest

from exploration.backend.budget import BudgetExceededError, BudgetGuard
from exploration.backend.retrieval import RetrievalClient, call_with_retries
from shared.contracts import InvestigationBudget


class StatusError(Exception):
    def __init__(self, status_code: int):
        super().__init__(f"status {status_code}")
        self.status_code = status_code


def test_dry_run_replays_synthetic_fixture_without_network(tmp_path):
    calls = {"search": 0, "fetch": 0}

    def search_fn(query, session_id):
        calls["search"] += 1
        raise AssertionError("network search")

    def fetch_fn(urls, session_id):
        calls["fetch"] += 1
        raise AssertionError("network fetch")

    client = RetrievalClient(
        cache_dir=tmp_path / "cache",
        dry_run=True,
        search_fn=search_fn,
        fetch_fn=fetch_fn,
        sleeper=lambda _seconds: None,
    )
    bundle = client.search("synthetic fixture query")
    assert calls["search"] == 0
    assert bundle.dry_run is True
    assert len(bundle.documents) == 1
    assert bundle.documents[0].providers == ["brave", "tavily"]
    assert bundle.documents[0].canonical_url == "https://example.com/widgets/report"
    assert bundle.session_id == "session_synthetic"
    missed = client.search("unseen query")
    assert missed.documents == []
    assert calls["search"] == 0
    pages = client.fetch(["https://example.com/missing"])
    assert calls["fetch"] == 0
    assert pages[0].error == "dry_run_miss"


def test_third_search_does_not_call_the_provider(tmp_path):
    calls = {"n": 0}

    def search_fn(query, session_id):
        calls["n"] += 1
        return {"session_id": "sess-1", "interaction_id": f"int-{calls['n']}", "provider_runs": []}

    client = RetrievalClient(cache_dir=tmp_path / "cache", dry_run=False, search_fn=search_fn, sleeper=lambda _s: None)
    guard = BudgetGuard(InvestigationBudget(max_searches=9))
    client.search("one", guard=guard)
    client.search("two", guard=guard)
    with pytest.raises(BudgetExceededError):
        client.search("three", guard=guard)
    assert calls["n"] == 2


def test_session_id_is_reused_and_retries_stop(tmp_path):
    seen = []

    def search_fn(query, session_id):
        seen.append(session_id)
        return {"session_id": "sess-1", "interaction_id": query, "provider_runs": [{"provider": "brave", "results": []}]}

    client = RetrievalClient(cache_dir=tmp_path / "cache", dry_run=False, search_fn=search_fn, sleeper=lambda _s: None)
    client.search("one")
    client.search("two")
    assert seen == [None, "sess-1"]

    attempts = {"n": 0}

    def flaky():
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise StatusError(503)
        return "ok"

    assert call_with_retries(flaky, sleeper=lambda _s: None, max_retries=2) == "ok"
    assert attempts["n"] == 3

    def rejected():
        raise StatusError(400)

    with pytest.raises(StatusError):
        call_with_retries(rejected, sleeper=lambda _s: None, max_retries=2)


def test_fetch_is_capped_and_tavily_runs_only_for_empty_content(tmp_path):
    fetches = {"n": 0}
    extracts = {"n": 0}

    def fetch_fn(urls, session_id):
        fetches["n"] += 1
        return {"results": [{"url": url, "content": "", "status": "empty", "provider": "telem"} for url in urls]}

    def extract(url: str) -> str:
        extracts["n"] += 1
        return f"extracted {url}"

    client = RetrievalClient(
        cache_dir=tmp_path / "cache",
        dry_run=False,
        fetch_fn=fetch_fn,
        tavily_extract_fn=extract,
        sleeper=lambda _s: None,
    )
    with pytest.raises(BudgetExceededError):
        client.fetch([f"https://example.com/{i}" for i in range(6)])
    assert fetches["n"] == 0
    pages = client.fetch(["https://example.com/empty"])
    assert fetches["n"] == 1
    assert extracts["n"] == 1
    assert pages[0].provider == "tavily_extract"
    assert pages[0].content.startswith("extracted ")
    again = client.fetch(["https://example.com/empty"])
    assert fetches["n"] == 1
    assert again[0].from_cache is True


def test_resume_fetch_does_not_repeat_unchanged_content(tmp_path):
    calls = {"n": 0}

    def fetch_fn(urls, session_id):
        calls["n"] += 1
        return {"results": [{"url": urls[0], "content": "Stable page content.", "status": "ok", "provider": "telem"}]}

    client = RetrievalClient(cache_dir=tmp_path / "cache", dry_run=False, fetch_fn=fetch_fn, sleeper=lambda _s: None)
    first = client.fetch(["https://example.com/stable"])
    second = client.fetch(["https://example.com/stable"])
    assert calls["n"] == 1
    assert first[0].content == second[0].content
    assert second[0].from_cache is True
