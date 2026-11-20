"""The same URL keeps the fuller page, not the short snippet."""

from __future__ import annotations

import sys
from pathlib import Path

FOCUS = Path(__file__).resolve().parents[2] / "focus"
sys.path.insert(0, str(FOCUS))

from focus_attention import FocusAttentionModel, Passage  # noqa: E402

PAGE = "NVIDIA has invested $2 billion in CoreWeave."


def test_same_url_keeps_the_fuller_page():
    model = FocusAttentionModel("NVIDIA CoreWeave investment")
    decisions = model.rank(
        [
            Passage("snippet", "Brief.", "https://news.example/a", title="Brief"),
            Passage("page", PAGE, "https://news.example/a", title="NVIDIA"),
        ]
    )
    texts = [item.passage.text for item in decisions]
    assert texts == [PAGE], texts
