"""Hard caps enforced by the exploration backend, independent of controller instructions."""

from __future__ import annotations

from shared.contracts import InvestigationBudget

from exploration.backend.config import (
    HARD_MAX_FETCH_BATCH,
    HARD_MAX_FETCHED_URLS,
    HARD_MAX_LLM_CALLS,
    HARD_MAX_SEARCHES,
)


class BudgetExceededError(RuntimeError):
    def __init__(self, kind: str):
        super().__init__(f"budget exceeded: {kind}")
        self.kind = kind


def clamp_budget(budget: InvestigationBudget | None) -> InvestigationBudget:
    raw = budget or InvestigationBudget()
    data = raw.model_dump()
    data["max_searches"] = min(max(raw.max_searches, 0), HARD_MAX_SEARCHES)
    data["max_fetched_urls"] = min(max(raw.max_fetched_urls, 0), HARD_MAX_FETCHED_URLS)
    data["max_llm_calls"] = min(max(raw.max_llm_calls, 0), HARD_MAX_LLM_CALLS)
    return InvestigationBudget.model_validate(data)


class BudgetGuard:
    """Refuse a third search, a sixth URL, an eleventh LLM call, or a 6-URL fetch batch."""

    def __init__(self, budget: InvestigationBudget):
        self.budget = budget

    def _store(self) -> None:
        self.budget = InvestigationBudget.model_validate(self.budget.model_dump())

    def authorize_search(self) -> None:
        cap = min(self.budget.max_searches, HARD_MAX_SEARCHES)
        if self.budget.searches_used >= cap:
            raise BudgetExceededError("search")
        self.budget.searches_used += 1
        self._store()

    def authorize_fetch(self, url_count: int) -> None:
        if url_count > HARD_MAX_FETCH_BATCH:
            raise BudgetExceededError("fetch_batch")
        cap = min(self.budget.max_fetched_urls, HARD_MAX_FETCHED_URLS)
        if url_count < 0 or self.budget.urls_fetched + url_count > cap:
            raise BudgetExceededError("fetched_urls")
        self.budget.urls_fetched += url_count
        self._store()

    def release_fetch(self, url_count: int) -> None:
        """Return URL slots for fetches that produced no page body."""
        if url_count <= 0:
            return
        self.budget.urls_fetched = max(0, self.budget.urls_fetched - url_count)
        self._store()

    def authorize_llm(self) -> None:
        cap = min(self.budget.max_llm_calls, HARD_MAX_LLM_CALLS)
        if self.budget.llm_calls_used >= cap:
            raise BudgetExceededError("llm")
        self.budget.llm_calls_used += 1
        self._store()
