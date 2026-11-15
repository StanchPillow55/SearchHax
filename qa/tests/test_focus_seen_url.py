"""A later fetch of a URL already ranked from a snippet is still ranked."""

from __future__ import annotations

import sys
from pathlib import Path

FOCUS = Path(__file__).resolve().parents[2] / "focus"
sys.path.insert(0, str(FOCUS))

from focus_attention import FocusAttentionModel, Passage  # noqa: E402

URL = "https://news.example/a"
PAGE = "NVIDIA has invested $2 billion in CoreWeave."


def test_later_page_for_a_seen_url_is_ranked():
    model = FocusAttentionModel("NVIDIA CoreWeave investment")
    model.rank([Passage("snippet", "Brief.", URL, title="Brief")])
    decisions = model.rank([Passage("page", PAGE, URL, title="NVIDIA")])
    texts = [item.passage.text for item in decisions]
    assert PAGE in texts, texts
