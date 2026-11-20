"""A different amount is not archived as a duplicate passage."""

from __future__ import annotations

import sys
from pathlib import Path

FOCUS = Path(__file__).resolve().parents[2] / "focus"
sys.path.insert(0, str(FOCUS))

from focus_attention import FocusAttentionModel, Passage  # noqa: E402

TWO = "NVIDIA has invested $2 billion in CoreWeave for the capacity buildout this year."
NINE = "NVIDIA has invested $9 billion in CoreWeave for the capacity buildout this year."


def test_different_amount_is_not_archived_as_a_duplicate():
    model = FocusAttentionModel("NVIDIA CoreWeave investment capacity")
    decisions = model.rank(
        [
            Passage("two", TWO, "https://news.example/two", title="Report"),
            Passage("nine", NINE, "https://news.example/nine", title="Report"),
        ]
    )
    by_url = {item.passage.url: item for item in decisions}
    nine = by_url["https://news.example/nine"]
    assert nine.action != "archive", (nine.action, round(nine.score.redundancy, 3), nine.reason)
