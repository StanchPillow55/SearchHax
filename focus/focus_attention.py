"""Source-aware focus attention for the convergence controller.

This module deliberately ranks evidence; it does not claim that a passage is
true.  Claim verification and retrieval adapters belong above this layer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
import math
import re
from typing import Iterable, Mapping, Sequence
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


_WORD_RE = re.compile(r"[a-z0-9]+")
_TRACKING_PARAMS = {"fbclid", "gclid", "mc_cid", "mc_eid"}


def _tokens(text: str) -> set[str]:
    return set(_WORD_RE.findall(text.lower()))


def _jaccard(left: str, right: str) -> float:
    a, b = _tokens(left), _tokens(right)
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def canonical_url(url: str) -> str:
    """Normalize a URL for source-level deduplication."""
    parts = urlsplit(url.strip())
    query = [(key, value) for key, value in parse_qsl(parts.query) if key not in _TRACKING_PARAMS and not key.startswith("utm_")]
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, urlencode(query), ""))


@dataclass(frozen=True)
class Passage:
    id: str
    text: str
    url: str
    title: str = ""
    providers: tuple[str, ...] = ()
    domain: str = ""
    published_at: date | datetime | None = None
    source_quality: float = 0.5
    embedding: tuple[float, ...] | None = None

    @property
    def source_key(self) -> str:
        return canonical_url(self.url)


@dataclass(frozen=True)
class AttentionScore:
    relevance: float
    graph_gap: float
    domain_fit: float
    freshness: float
    novelty: float
    redundancy: float
    source_value: float
    attention: float


@dataclass(frozen=True)
class FocusDecision:
    passage: Passage
    score: AttentionScore
    action: str  # consider, investigate, archive
    reason: str


@dataclass
class FocusState:
    accepted: list[FocusDecision] = field(default_factory=list)
    investigate: list[FocusDecision] = field(default_factory=list)
    archived: list[FocusDecision] = field(default_factory=list)


class FocusAttentionModel:
    """Rank and route candidate evidence according to a bounded focus policy.

    ``exploration`` is a policy control from 0 (focused) to 1 (exploratory).
    It changes novelty tolerance only; it is never treated as truth or claim
    confidence.
    """

    def __init__(
        self,
        intent: str,
        *,
        unresolved_questions: Sequence[str] = (),
        domain_terms: Sequence[str] = (),
        exploration: float = 0.5,
        now: date | datetime | None = None,
    ) -> None:
        if not intent.strip():
            raise ValueError("intent must not be empty")
        if not 0 <= exploration <= 1:
            raise ValueError("exploration must be between 0 and 1")
        self.intent = intent.strip()  # immutable after construction by design
        self.unresolved_questions = tuple(unresolved_questions)
        self.domain_terms = frozenset(_tokens(" ".join(domain_terms)))
        self.exploration = exploration
        self.now = now or date.today()
        self.state = FocusState()

    @property
    def novelty_threshold(self) -> float:
        # At the README's 50% setting, ordinary consideration accepts ~55%
        # novelty. The slider changes search behavior, not factual confidence.
        return 0.30 + 0.50 * self.exploration

    def score(self, passage: Passage) -> AttentionScore:
        relevance = self._similarity(self.intent, passage)
        gap = max((self._similarity(question, passage) for question in self.unresolved_questions), default=0.0)
        passage_terms = _tokens(f"{passage.title} {passage.text}")
        domain_fit = (len(passage_terms & self.domain_terms) / len(self.domain_terms)) if self.domain_terms else 0.5
        freshness = self._freshness(passage.published_at)
        known = [item.passage for item in self.state.accepted + self.state.investigate]
        redundancy = max((self._similarity(item.text, passage) for item in known), default=0.0)
        novelty = 1.0 - redundancy
        provenance = min(len(set(passage.providers)) / 3.0, 1.0)
        source_value = max(0.0, min(1.0, 0.7 * passage.source_quality + 0.3 * provenance))
        attention = 0.4 * relevance + 0.3 * gap + 0.2 * domain_fit + 0.1 * freshness
        return AttentionScore(relevance, gap, domain_fit, freshness, novelty, redundancy, source_value, attention)

    def decide(self, passage: Passage) -> FocusDecision:
        score = self.score(passage)
        if score.relevance < 0.20 or (score.relevance < 0.35 and score.graph_gap < 0.35):
            action, reason = "archive", "low intent alignment"
        elif score.novelty >= self.novelty_threshold and score.relevance >= 0.35:
            action, reason = "investigate", "novel and intent-relevant; route for verification"
        elif score.redundancy >= 0.80:
            action, reason = "archive", "redundant with accepted evidence"
        else:
            action, reason = "consider", "relevant evidence within the current focus boundary"
        return FocusDecision(passage, score, action, reason)

    def rank(self, passages: Iterable[Passage]) -> list[FocusDecision]:
        """Deduplicate by canonical URL, route candidates, and update context."""
        unique: dict[str, Passage] = {}
        for passage in passages:
            unique.setdefault(passage.source_key, passage)
        decisions = [self.decide(passage) for passage in unique.values()]
        decisions.sort(key=lambda item: item.score.attention, reverse=True)
        for decision in decisions:
            bucket = {"consider": self.state.accepted, "investigate": self.state.investigate, "archive": self.state.archived}[decision.action]
            bucket.append(decision)
        return decisions

    def _similarity(self, text: str, passage: Passage) -> float:
        if passage.embedding is not None:
            # Embeddings are accepted for future adapters; query embeddings are
            # intentionally not fabricated here, so lexical scoring is used.
            return _jaccard(text, passage.text + " " + passage.title)
        return _jaccard(text, passage.text + " " + passage.title)

    def _freshness(self, published_at: date | datetime | None) -> float:
        if published_at is None:
            return 0.5
        published = published_at.date() if isinstance(published_at, datetime) else published_at
        current = self.now.date() if isinstance(self.now, datetime) else self.now
        age_days = max(0, (current - published).days)
        return math.exp(-age_days / 365.0)
