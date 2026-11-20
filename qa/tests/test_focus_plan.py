"""An investigate follow-up has to run inside the default search budget."""

from __future__ import annotations

import sys
from pathlib import Path

FOCUS = Path(__file__).resolve().parents[2] / "focus"
sys.path.insert(0, str(FOCUS))

from focus_attention import FocusAttentionModel, Passage  # noqa: E402
from research_loop import followup_query, run_research  # noqa: E402

# The angles focus/app.py queues for a deep investigation.
PLAN = tuple(
    f"electric vehicle demand {angle}"
    for angle in (
        "main causes evidence",
        "evidence challenging the premise",
        "recent statistics and trends",
        "consumer behavior and affordability",
        "industry response and forecasts",
    )
)


def test_investigate_follow_up_runs_inside_the_default_budget():
    """Budget 3 is the app default. A passage routed to investigate is searched."""
    model = FocusAttentionModel("electric vehicle demand", exploration=1.0)

    def retrieve(query: str) -> list[Passage]:
        del query
        if not retrieve.called:
            retrieve.called = True
            return [
                Passage("a", "electric vehicle demand decreases", "https://a.example", title="EV demand"),
                Passage(
                    "b",
                    "electric vehicle demand battery resale value",
                    "https://b.example",
                    title="Battery resale",
                ),
            ]
        return []

    retrieve.called = False
    result = run_research(
        model,
        retrieve,
        max_search_calls=3,
        max_stagnant_batches=3,
        query_plan=PLAN,
    )
    investigated = [decision for decision in result.decisions if decision.action == "investigate"]
    assert investigated
    expected = followup_query(investigated[0], model.intent)
    assert expected in result.queries, result.queries
