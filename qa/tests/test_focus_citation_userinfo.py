"""A cited answer does not publish a URL secret."""

from __future__ import annotations

import sys
from pathlib import Path

FOCUS = Path(__file__).resolve().parents[2] / "focus"
sys.path.insert(0, str(FOCUS))

from answer_composer import compose_answer  # noqa: E402
from focus_attention import FocusAttentionModel, Passage  # noqa: E402


def test_cited_answer_does_not_publish_url_userinfo():
    model = FocusAttentionModel("why is electric vehicle demand weakening")
    decisions = model.rank(
        [
            Passage(
                "price",
                "High prices and interest rates can reduce EV demand.",
                "https://user:secret@news.example/price",
                title="EV affordability",
            )
        ]
    )
    result = compose_answer(
        "why is electric vehicle demand weakening",
        decisions,
        transport=lambda _payload: {"output_text": "Affordability matters [S1]."},
    )
    assert "secret" not in result.markdown, result.markdown
    assert "https://news.example/price" in result.markdown
