"""A failure from one provider must not discard the other provider's pages."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

FOCUS = Path(__file__).resolve().parents[2] / "focus"
sys.path.insert(0, str(FOCUS))

import retrieval_adapters  # noqa: E402
from focus_attention import Passage  # noqa: E402


def test_one_provider_failure_keeps_the_other_providers_pages(monkeypatch: pytest.MonkeyPatch):
    """Telem's page survives when Tavily raises during a Both search."""
    seen: list[str] = []

    def telem_search(query: str, max_results: int = 8) -> list[Passage]:
        del query, max_results
        seen.append("telem")
        return [
            Passage(
                "telem-page",
                "electric vehicle demand prices",
                "https://telem.example",
                providers=("telem",),
            )
        ]

    def tavily_search(query: str, max_results: int = 8) -> list[Passage]:
        del query, max_results
        seen.append("tavily")
        raise RuntimeError("tavily unavailable")

    monkeypatch.setattr(retrieval_adapters, "telem_search", telem_search)
    monkeypatch.setattr(retrieval_adapters, "tavily_search", tavily_search)
    raised = None
    rows: list[Passage] = []
    try:
        rows = retrieval_adapters.search("electric vehicle demand", "both")
    except Exception as exc:
        raised = type(exc).__name__
    assert raised is None, (raised, [row.url for row in rows], seen)
    assert [row.url for row in rows] == ["https://telem.example"]
