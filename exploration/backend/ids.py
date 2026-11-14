"""Stable identifiers derived from content, not from insertion order."""

from __future__ import annotations

import hashlib
import uuid


def stable_id(prefix: str, *parts: str) -> str:
    raw = "\n".join(parts)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}_{digest}"


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:16]}"
