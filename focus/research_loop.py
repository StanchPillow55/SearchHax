"""Bounded discovery loop: verification *search*, not verified truth."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Callable
from focus_attention import FocusAttentionModel, FocusDecision, Passage


@dataclass
class ResearchRun:
    decisions: list[FocusDecision]
    queries: list[str]
    search_calls: int
    accepted: int
    queued: int
    stopped: bool


def followup_query(decision: FocusDecision, original_intent: str) -> str:
    """Transparent keyword query; replace with LLM planner if desired."""
    headline = decision.passage.title or decision.passage.text[:110]
    return f'{original_intent} {headline} supporting evidence conflicting evidence'


def run_research(model: FocusAttentionModel,
                 retrieve: Callable[[str], list[Passage]],
                 *, max_search_calls: int = 3,
                 max_stagnant_batches: int = 2) -> ResearchRun:
    """Fetch, rank, and target novel findings within a strict request budget.

    Results from follow-ups are new *candidates*, not verified evidence.
    The selected novel claim remains in investigate until separately reviewed.
    """
    all_decisions: list[FocusDecision] = []
    queries: list[str] = []
    pending = [model.intent]
    processed_investigations: set[str] = set()
    while pending and not model.should_stop(
            max_search_calls=max_search_calls,
            max_stagnant_batches=max_stagnant_batches):
        query = pending.pop(0)
        passages = retrieve(query)
        model.record_search_call()
        decisions = model.rank(passages)
        queries.append(query)
        all_decisions.extend(decisions)
        for decision in decisions:
            if decision.action == 'investigate' and decision.passage.source_key not in processed_investigations:
                processed_investigations.add(decision.passage.source_key)
                pending.append(followup_query(decision, model.intent))
        # No automatic broad re-search on an empty queue. A targeted investigation
        # is run only when there is something specifically worth examining.
    return ResearchRun(decisions=all_decisions, queries=queries,
        search_calls=model.state.search_calls,
        accepted=len(model.state.accepted), queued=len(model.state.investigate),
        stopped=model.should_stop(max_search_calls=max_search_calls,
                                  max_stagnant_batches=max_stagnant_batches))
