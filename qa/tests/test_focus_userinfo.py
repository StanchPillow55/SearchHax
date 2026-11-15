"""A URL userinfo secret is not kept in the canonical source key."""

from __future__ import annotations

import sys
from pathlib import Path

FOCUS = Path(__file__).resolve().parents[2] / "focus"
sys.path.insert(0, str(FOCUS))

from focus_attention import canonical_url  # noqa: E402


def test_url_userinfo_is_not_part_of_the_source_key():
    canonical = canonical_url("https://user:secret@news.example/a")
    assert canonical == "https://news.example/a", canonical
    assert "secret" not in canonical
