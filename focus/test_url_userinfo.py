"""URL credentials (user:password@) never reach a source key or a citation.

Ported from the QA defect ledger (qa/exploration-verification): test_focus_userinfo,
test_focus_citation_userinfo.
"""

from __future__ import annotations

import sys
from pathlib import Path

FOCUS = Path(__file__).resolve().parent
sys.path.insert(0, str(FOCUS))

from answer_composer import compose_answer  # noqa: E402
from focus_attention import FocusAttentionModel, Passage, canonical_url  # noqa: E402


def test_url_userinfo_is_not_part_of_the_source_key():
    canonical = canonical_url("https://user:secret@news.example/a")
    assert canonical == "https://news.example/a", canonical
    assert "secret" not in canonical


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


def test_exploration_source_keys_drop_userinfo():
    from exploration.backend.retrieval import normalize_url

    assert normalize_url("https://user:secret@News.example/a/") == "https://news.example/a"
