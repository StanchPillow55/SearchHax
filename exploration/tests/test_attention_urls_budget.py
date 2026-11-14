from datetime import date

import pytest

from exploration.backend.attention import score_passage
from exploration.backend.budget import BudgetExceededError, BudgetGuard
from exploration.backend.retrieval import ProviderHit, independent_source_count, merge_provider_hits, normalize_url
from shared.contracts import InvestigationBudget


def test_url_normalization_strips_fragment_slash_and_lowercases_host():
    assert normalize_url("HTTPS://Example.COM/a/b/#section") == "https://example.com/a/b"
    assert normalize_url("https://example.com/a/b/") == "https://example.com/a/b"
    assert normalize_url("https://example.com/a/b/?q=1#x") == "https://example.com/a/b?q=1"
    assert normalize_url("https://Example.com/") == "https://example.com/"


def test_provider_dedup_keeps_provider_identity_as_one_source():
    hits = [
        ProviderHit(provider="brave", url="https://Example.com/a/#top", canonical_url=normalize_url("https://Example.com/a/#top"), title="A", snippet="one"),
        ProviderHit(provider="tavily", url="https://example.com/a/", canonical_url=normalize_url("https://example.com/a/"), title="A", snippet="two"),
    ]
    documents = merge_provider_hits(hits)
    assert len(documents) == 1
    assert documents[0].providers == ["brave", "tavily"]
    assert len(documents[0].hits) == 2
    assert independent_source_count(documents) == 1


def test_attention_score_is_bounded_and_matches_formula():
    scored = score_passage("alpha beta", "alpha beta gamma", ["gamma"], None, date(2026, 11, 14))
    assert scored.R == pytest.approx(1.0)
    assert scored.G == pytest.approx(1.0)
    assert scored.D == 0.0
    assert scored.F == 0.0
    assert scored.score == pytest.approx(0.4 * scored.R + 0.3 * scored.G + 0.2 * scored.D + 0.1 * scored.F)
    assert 0.0 <= scored.score <= 1.0
    bridged = score_passage("investment outlook", "a customer filed demand data", None, "2026-11-01")
    assert bridged.D == 1.0
    assert 0.0 <= bridged.F <= 1.0
    stale = score_passage("alpha", "alpha", None, "2010-01-01")
    assert stale.F == 0.0
    empty = score_passage("", "", None, "not-a-date")
    for value in (empty.R, empty.G, empty.D, empty.F, empty.score):
        assert 0.0 <= value <= 1.0
    assert "not factual confidence" in (scored.model_fields["score"].description or "").lower()


def test_third_search_is_refused_even_if_controller_budget_is_higher():
    guard = BudgetGuard(InvestigationBudget(max_searches=10))
    guard.authorize_search()
    guard.authorize_search()
    with pytest.raises(BudgetExceededError) as caught:
        guard.authorize_search()
    assert caught.value.kind == "search"
    assert guard.budget.searches_used == 2
    fetch_guard = BudgetGuard(InvestigationBudget(max_fetched_urls=100, max_llm_calls=100))
    with pytest.raises(BudgetExceededError) as batch:
        fetch_guard.authorize_fetch(6)
    assert batch.value.kind == "fetch_batch"
    for _ in range(10):
        fetch_guard.authorize_llm()
    with pytest.raises(BudgetExceededError):
        fetch_guard.authorize_llm()
