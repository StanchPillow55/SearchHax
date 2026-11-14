"""Deterministic evidence attention.

A(q, p) = 0.4*R + 0.3*G + 0.2*D + 0.1*F

R is query-token overlap, G is overlap with unresolved gaps, D is a small
domain-keyword bridge list, and F is recency from publish_date. Every
component and the final score are in [0, 1].

Attention is a retrieval-priority heuristic. It is not factual confidence,
not claim verification, and not a probability that a passage is true.
"""

from __future__ import annotations

import re
from datetime import date, datetime

from shared.contracts import AttentionComponents

WEIGHT_R = 0.4
WEIGHT_G = 0.3
WEIGHT_D = 0.2
WEIGHT_F = 0.1

# Trigger term -> bridge terms. A hit means the passage may connect the query
# to a neighboring domain. This list is a heuristic, not a trained model.
DOMAIN_BRIDGES: dict[str, tuple[str, ...]] = {
    "gpu": ("datacenter", "power", "packaging", "hbm", "capacity"),
    "nvidia": ("coreweave", "gpu", "foundry", "investment", "capacity"),
    "investment": ("customer", "demand", "financing", "capacity"),
    "semiconductor": ("substrate", "ceramic", "packaging", "warpage"),
    "financing": ("demand", "customer", "capacity", "campus"),
    "lumenarc": ("helios", "campus", "financing", "wire"),
    "infrastructure": ("power", "capacity", "customer", "demand"),
}

_TOKEN = re.compile(r"[a-z0-9]+")
REFERENCE_DATE = date(2026, 11, 14)


def clamp01(value: float) -> float:
    if value != value:  # NaN
        return 0.0
    return max(0.0, min(1.0, float(value)))


def tokenize(text: str) -> set[str]:
    return {token for token in _TOKEN.findall(text.lower()) if len(token) >= 2}


def _coverage(needles: set[str], haystack: set[str]) -> float:
    if not needles:
        return 0.0
    return clamp01(len(needles & haystack) / len(needles))


def query_relevance(query: str, passage: str) -> float:
    return _coverage(tokenize(query), tokenize(passage))


def gap_overlap(passage: str, gaps: list[str] | None) -> float:
    if not gaps:
        return 0.0
    passage_tokens = tokenize(passage)
    scores = [_coverage(tokenize(gap), passage_tokens) for gap in gaps if tokenize(gap)]
    return max(scores) if scores else 0.0


def domain_bridge(query: str, passage: str) -> float:
    query_tokens = tokenize(query)
    passage_tokens = tokenize(passage)
    for trigger, bridges in DOMAIN_BRIDGES.items():
        if trigger in query_tokens and any(bridge in passage_tokens for bridge in bridges):
            return 1.0
    return 0.0


def parse_publish_date(value: str | None) -> date | None:
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        pass
    try:
        return datetime.strptime(text[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def freshness(publish_date: str | None, today: date = REFERENCE_DATE) -> float:
    """1.0 within 30 days, declining to 0.0 at three years. Unknown dates score 0."""
    published = parse_publish_date(publish_date)
    if published is None:
        return 0.0
    age_days = (today - published).days
    if age_days <= 30:
        return 1.0
    horizon = 365 * 3
    if age_days >= horizon:
        return 0.0
    return clamp01(1.0 - ((age_days - 30) / (horizon - 30)))


def score_passage(
    query: str,
    passage: str,
    gaps: list[str] | None = None,
    publish_date: str | None = None,
    today: date = REFERENCE_DATE,
) -> AttentionComponents:
    """Return attention components. The score is not a confidence value."""
    relevance = query_relevance(query, passage)
    gaps_score = gap_overlap(passage, gaps)
    domain = domain_bridge(query, passage)
    fresh = freshness(publish_date, today)
    score = clamp01(
        WEIGHT_R * relevance + WEIGHT_G * gaps_score + WEIGHT_D * domain + WEIGHT_F * fresh
    )
    return AttentionComponents(R=relevance, G=gaps_score, D=domain, F=fresh, score=score)
