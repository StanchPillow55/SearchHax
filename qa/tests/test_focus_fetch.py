"""Focus fetch must not turn a failed page body into cited evidence."""

from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

FOCUS = Path(__file__).resolve().parents[2] / "focus"
sys.path.insert(0, str(FOCUS))

from retrieval_adapters import hydrate_decisions, telem_fetch  # noqa: E402
from focus_attention import FocusAttentionModel, FocusDecision, Passage  # noqa: E402


def _install_fetch(monkeypatch: pytest.MonkeyPatch, payload: dict) -> None:
    monkeypatch.setenv("TELEM_API_KEY", "qa-dummy")
    fake = types.ModuleType("requests")

    class Response:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return payload

    def post(*_args, **_kwargs):
        return Response()

    fake.post = post
    monkeypatch.setitem(sys.modules, "requests", fake)


def test_failed_fetch_body_is_not_used_as_page_text(monkeypatch):
    """A failed URL with a body is skipped. The search snippet stays in place."""
    url = "https://news.example/missing"
    body = "404 Not Found. NVIDIA has invested $2 billion in CoreWeave."
    _install_fetch(
        monkeypatch,
        {"results": [{"url": url, "status": "failed", "error": "HTTP 404", "content": body}]},
    )
    fetched = telem_fetch([url])
    assert url not in fetched
    assert body not in fetched.values()

    passage = Passage("snippet", "Search snippet only.", url)
    model = FocusAttentionModel("NVIDIA CoreWeave investment")
    decision = FocusDecision(passage, model.score(passage), "consider", "candidate")
    hydrated = hydrate_decisions([decision])
    assert hydrated[0].passage.text == "Search snippet only."
