"""Independent checks for retrieval contracts and attention scoring."""

from __future__ import annotations

import pytest

from exploration.backend.attention import score_passage
from exploration.backend.budget import BudgetExceededError, BudgetGuard
from exploration.backend.retrieval import (
    ProviderHit,
    RetrievalClient,
    call_with_retries,
    independent_source_count,
    merge_provider_hits,
    normalize_url,
)
from shared.contracts import AttentionComponents, InvestigationBudget


class StatusError(Exception):
    def __init__(self, status_code: int):
        super().__init__(f"status {status_code}")
        self.status_code = status_code


def test_url_normalization_collapses_fragment_host_and_trailing_slash():
    assert normalize_url("HTTPS://Example.COM/a/b/#section") == "https://example.com/a/b"
    assert normalize_url("https://example.com/a/b/") == "https://example.com/a/b"
    assert normalize_url("https://example.com/a/b/?q=1#x") == normalize_url("https://example.com/a/b?q=1")


def test_duplicate_provider_hits_keep_metadata_and_count_as_one_source():
    left = ProviderHit(
        provider="brave",
        url="https://Example.com/report/#top",
        canonical_url=normalize_url("https://Example.com/report/#top"),
        title="Report",
        snippet="Brave snippet",
        publish_date="2026-03-04",
        rank=1,
    )
    right = ProviderHit(
        provider="tavily",
        url="https://example.com/report/",
        canonical_url=normalize_url("https://example.com/report/"),
        title="",
        snippet="Tavily snippet",
        rank=2,
    )
    documents = merge_provider_hits([left, right])
    assert len(documents) == 1
    assert documents[0].providers == ["brave", "tavily"]
    assert [hit.provider for hit in documents[0].hits] == ["brave", "tavily"]
    assert documents[0].publish_date == "2026-03-04"
    assert independent_source_count(documents) == 1


def test_non_transient_errors_are_not_retried_and_rate_limits_stop():
    calls = {"n": 0}

    def limited():
        calls["n"] += 1
        raise StatusError(429)

    with pytest.raises(StatusError):
        call_with_retries(limited, sleeper=lambda _seconds: None, max_retries=2)
    assert calls["n"] == 3

    calls["n"] = 0

    def rejected():
        calls["n"] += 1
        raise StatusError(400)

    with pytest.raises(StatusError):
        call_with_retries(rejected, sleeper=lambda _seconds: None, max_retries=2)
    assert calls["n"] == 1


def test_session_lineage_is_reused_and_search_budget_is_enforced(tmp_path):
    seen: list[str | None] = []

    def search_fn(query: str, session_id: str | None):
        seen.append(session_id)
        return {
            "session_id": "sess-qa",
            "interaction_id": f"int-{len(seen)}",
            "by_provider": [{"provider": "brave", "status": "ok", "results": []}],
        }

    client = RetrievalClient(
        cache_dir=tmp_path / "cache",
        dry_run=False,
        search_fn=search_fn,
        sleeper=lambda _seconds: None,
        tavily_extract_fn=lambda _url: "",
    )
    guard = BudgetGuard(InvestigationBudget(max_searches=9))
    first = client.search("one", guard=guard)
    second = client.search("two", guard=guard)
    with pytest.raises(BudgetExceededError):
        client.search("three", guard=guard)
    assert seen == [None, "sess-qa"]
    assert first.session_id == "sess-qa"
    assert second.interaction_id == "int-2"
    assert client.interaction_ids == ["int-1", "int-2"]
    assert guard.budget.searches_used == 2


def test_fetch_batch_cap_and_cache_reuse(tmp_path):
    fetches = {"n": 0}

    def fetch_fn(urls: list[str], session_id: str | None):
        fetches["n"] += 1
        return {
            "results": [
                {"url": url, "content": f"body {url}", "status": "ok", "provider": "telem"}
                for url in urls
            ]
        }

    client = RetrievalClient(
        cache_dir=tmp_path / "cache",
        dry_run=False,
        fetch_fn=fetch_fn,
        sleeper=lambda _seconds: None,
        tavily_extract_fn=lambda _url: "",
    )
    with pytest.raises(BudgetExceededError):
        client.fetch([f"https://example.com/{index}" for index in range(6)])
    assert fetches["n"] == 0
    first = client.fetch(["https://example.com/page"])
    second = client.fetch(["https://example.com/page"])
    assert fetches["n"] == 1
    assert second[0].from_cache is True
    assert second[0].content == first[0].content


def test_attention_formula_bounds_and_gap_effect():
    plain = score_passage("alpha beta", "alpha beta", None, None)
    gapped = score_passage("alpha beta", "alpha beta zeta", ["zeta"], None)
    assert plain.score == pytest.approx(0.4 * plain.R + 0.3 * plain.G + 0.2 * plain.D + 0.1 * plain.F)
    assert gapped.G > plain.G
    assert gapped.score > plain.score
    for scored in (plain, gapped):
        for value in (scored.R, scored.G, scored.D, scored.F, scored.score):
            assert 0.0 <= value <= 1.0
    with pytest.raises(ValueError):
        AttentionComponents(R=1, G=1, D=1, F=1, score=1.1)
    description = (plain.model_fields["score"].description or "").lower()
    assert "not factual confidence" in description
