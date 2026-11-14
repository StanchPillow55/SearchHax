"""A cited answer must not keep an unknown citation marker."""

from __future__ import annotations

import sys
from pathlib import Path

FOCUS = Path(__file__).resolve().parents[2] / "focus"
sys.path.insert(0, str(FOCUS))

from answer_composer import AnswerGenerationError, compose_answer  # noqa: E402
from focus_attention import FocusAttentionModel, Passage  # noqa: E402


def test_unknown_marker_is_not_shown_with_a_valid_citation():
    """The app's non-strict path still has to reject [S99] when [S1] is present."""
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
    text = "An invented statistic [S99]. Affordability matters [S1]."
    try:
        result = compose_answer(
            "why is electric vehicle demand weakening",
            decisions,
            strict_citations=False,
            transport=lambda _payload: {"output_text": text},
        )
    except AnswerGenerationError:
        return
    assert "[S99]" not in result.markdown
    assert result.cited_source_ids == ("S1",)
