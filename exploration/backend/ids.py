"""Stable identifiers derived from content, not from insertion order."""

from __future__ import annotations

import hashlib
import uuid


def stable_id(prefix: str, *parts: str) -> str:
    # Parts are joined with a newline, so a newline (or backslash) inside a part
    # is escaped first; otherwise ("a\nb", "c") and ("a", "b\nc") would collide.
    # Parts without either character hash exactly as before.
    raw = "\n".join(part.replace("\\", "\\\\").replace("\n", "\\n") for part in parts)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}_{digest}"


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:16]}"
