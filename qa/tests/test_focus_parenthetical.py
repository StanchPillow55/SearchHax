"""A bare parenthetical number is not a citation of a source."""

from __future__ import annotations

import sys
from pathlib import Path

FOCUS = Path(__file__).resolve().parents[2] / "focus"
sys.path.insert(0, str(FOCUS))

from answer_composer import compose_answer  # noqa: E402
from focus_attention import FocusAttentionModel, Passage  # noqa: E402


def test_quarter_number_is_not_a_source_citation():
    """"(1)" in "quarter (1)" must not become a citation of the only source."""
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
        transport=lambda _payload: {"output_text": "Demand fell in quarter (1)."},
    )
    assert "(1)" in result.markdown
    assert result.cited_source_ids == ()
