"""A titled page with an empty body is still ranked."""

from __future__ import annotations

import sys
from pathlib import Path

FOCUS = Path(__file__).resolve().parents[2] / "focus"
sys.path.insert(0, str(FOCUS))

from focus_attention import FocusAttentionModel, Passage  # noqa: E402


def test_empty_body_with_a_title_is_ranked():
    model = FocusAttentionModel("NVIDIA CoreWeave investment")
    decisions = model.rank(
        [
            Passage(
                "p",
                "   ",
                "https://news.example/a",
                title="NVIDIA has invested $2 billion in CoreWeave",
            )
        ]
    )
    urls = [item.passage.url for item in decisions]
    assert urls == ["https://news.example/a"], [(item.passage.url, item.action) for item in decisions]
