"""A longer URL must not be rewritten into a citation of a shorter source URL."""

from __future__ import annotations

import sys
from pathlib import Path

FOCUS = Path(__file__).resolve().parents[2] / "focus"
sys.path.insert(0, str(FOCUS))

from answer_composer import compose_answer  # noqa: E402
from focus_attention import FocusAttentionModel, Passage  # noqa: E402


def test_longer_url_is_not_cited_as_the_shorter_source():
    """https://example.com/price-war is not source https://example.com/price."""
    model = FocusAttentionModel("why is electric vehicle demand weakening")
    decisions = model.rank(
        [
            Passage(
                "price",
                "High prices and interest rates can reduce EV demand.",
                "https://example.com/price",
                title="EV affordability",
            )
        ]
    )
    result = compose_answer(
        "why is electric vehicle demand weakening",
        decisions,
        strict_citations=False,
        transport=lambda _payload: {
            "output_text": "A different page https://example.com/price-war says demand rose."
        },
    )
    assert "https://example.com/price-war" in result.markdown
    assert "[S1]-war" not in result.markdown
    assert result.cited_source_ids == ()
