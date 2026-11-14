"""The focus research loop must not spend its search budget on a repeated query."""

from __future__ import annotations

import sys
from pathlib import Path

FOCUS = Path(__file__).resolve().parents[2] / "focus"
sys.path.insert(0, str(FOCUS))

from focus_attention import FocusAttentionModel, Passage  # noqa: E402
from research_loop import run_research  # noqa: E402


def test_identical_follow_up_is_issued_once():
    """Two investigate passages with one title produce one follow-up search."""
    model = FocusAttentionModel("electric vehicle demand", exploration=1.0)
    calls: list[str] = []

    def retrieve(query: str) -> list[Passage]:
        calls.append(query)
        if len(calls) == 1:
            return [
                Passage("a", "electric vehicle demand decreases", "https://a.example", title="EV demand"),
                Passage("b", "electric vehicle demand battery resale value", "https://b.example", title="EV demand"),
                Passage("c", "electric vehicle demand charging prices", "https://c.example", title="EV demand"),
            ]
        return []

    result = run_research(model, retrieve, max_search_calls=3)
    assert result.search_calls == len(calls)
    assert len(calls) == len(set(calls)), calls
