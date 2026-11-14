"""Intent-anchored evidence selection, NOT verification or truth estimation.

The optional embedder exposes encode(list[str]) -> array-like of vectors.
Without one, transparent lexical Jaccard scoring is used. The original intent
is read-only; accepted and unverified evidence are maintained separately.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date, datetime
from typing import Iterable, Sequence, Protocol
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
import math
import re

_WORD_RE = re.compile(r"[a-z0-9]+")
_TRACKING = {"fbclid", "gclid", "mc_cid", "mc_eid"}


def _tokens(text: str) -> set[str]:
    words = set(_WORD_RE.findall(text.lower()))
    # Small, deterministic normalization for search snippets. In particular,
    # search providers commonly use "EV" where the intent says "electric
    # vehicle"; without this expansion, otherwise relevant results can fall
    # below the intent floor simply because the snippet is longer.
    if "ev" in words:
        words.update({"electric", "vehicle"})
    words.update(word[:-1] for word in tuple(words) if len(word) > 4 and word.endswith("s"))
    return words


def _jaccard(a: str, b: str) -> float:
    x, y = _tokens(a), _tokens(b)
    return len(x & y) / len(x | y) if x and y else 0.0


def _query_coverage(query: str, document: str) -> float:
    """Measure intent-token coverage without penalizing long result snippets."""
    query_tokens, document_tokens = _tokens(query), _tokens(document)
    return len(query_tokens & document_tokens) / len(query_tokens) if query_tokens else 0.0


def canonical_url(url: str) -> str:
    """Normalize known trackers, host case, default port and URL fragments."""
    parts = urlsplit(url.strip())
    scheme = parts.scheme.lower()
    netloc = parts.netloc.lower()
    if (scheme == "https" and netloc.endswith(":443")) or (scheme == "http" and netloc.endswith(":80")):
        netloc = netloc.rsplit(":", 1)[0]
    path = parts.path.rstrip("/") or "/"
    query = sorted((k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
                   if k.lower() not in _TRACKING and not k.lower().startswith("utm_"))
    return urlunsplit((scheme, netloc, path, urlencode(query), ""))


def _normalized(vector: Sequence[float]) -> tuple[float, ...]:
    values = tuple(float(v) for v in vector)
    magnitude = math.sqrt(sum(v * v for v in values))
    if not values or magnitude <= 1e-12 or not all(math.isfinite(v) for v in values):
        raise ValueError("embedding must be a finite nonzero vector")
    return tuple(v / magnitude for v in values)


def _cosine_positive(a: Sequence[float], b: Sequence[float]) -> float:
    if len(a) != len(b):
        raise ValueError("embedding dimensions do not match")
    return max(0.0, min(1.0, sum(x * y for x, y in zip(a, b))))


class Embedder(Protocol):
    def encode(self, texts: list[str]) -> Sequence[Sequence[float]]: ...


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
        return canonical_url(self.url) if self.url.strip() else f"id:{self.id}"

    @property
    def searchable(self) -> str:
        return f"{self.title} {self.text}".strip()


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
    seen_keys: set[str] = field(default_factory=set)
    stagnant_batches: int = 0
    search_calls: int = 0


class FocusAttentionModel:
    """Greedy evidence selection with an immutable original-intent anchor.

    Exploration controls *verification effort* for unusual but relevant sources.
    It never changes semantic relevance or establishes factual correctness.
    The source-quality prior is user-supplied and not a verification result.
    """

    def __init__(self, intent: str, *, unresolved_questions: Sequence[str] = (),
                 domain_terms: Sequence[str] = (), exploration: float = 0.5,
                 now: date | datetime | None = None, embedder: Embedder | None = None,
                 redundancy_threshold: float = 0.85,
                 intent_floor: float = 0.20) -> None:
        if not intent.strip():
            raise ValueError("intent must not be empty")
        if not 0 <= exploration <= 1:
            raise ValueError("exploration must be between 0 and 1")
        if not 0 <= redundancy_threshold <= 1 or not 0 <= intent_floor <= 1:
            raise ValueError("thresholds must be between 0 and 1")
        self._intent = intent.strip()
        self.unresolved_questions = tuple(unresolved_questions)
        self.domain_terms = frozenset(_tokens(" ".join(domain_terms)))
        self.exploration = float(exploration)
        self.now = now or date.today()
        self.embedder = embedder
        self.redundancy_threshold = redundancy_threshold
        self.intent_floor = intent_floor
        self.state = FocusState()
        self._vector_cache: dict[str, tuple[float, ...]] = {}
        self._query_vectors: dict[str, tuple[float, ...]] = {}
        if embedder is not None:
            texts = [self._intent, *self.unresolved_questions]
            vectors = self._encode_many(texts)
            self._query_vectors = dict(zip(texts, vectors))

    @property
    def intent(self) -> str:
        return self._intent

    @property
    def novelty_threshold(self) -> float:
        """Above this distance, *eligible* sources enter investigation queue."""
        return 0.75 - 0.40 * self.exploration

    @property
    def investigation_budget(self) -> int:
        """Maximum new investigations per retrieval batch."""
        return math.ceil(self.exploration * 5)

    def _encode_many(self, texts: list[str]) -> list[tuple[float, ...]]:
        if self.embedder is None or not texts:
            return []
        raw = self.embedder.encode(texts)
        if len(raw) != len(texts):
            raise ValueError("embedder returned wrong number of vectors")
        return [_normalized(v) for v in raw]

    def _prepare(self, passages: Sequence[Passage]) -> None:
        if self.embedder is None:
            return
        missing = [p.searchable for p in passages if p.embedding is None and p.searchable not in self._vector_cache]
        if missing:
            unique = list(dict.fromkeys(missing))
            self._vector_cache.update(zip(unique, self._encode_many(unique)))

    def _passage_vector(self, p: Passage) -> tuple[float, ...]:
        if p.embedding is not None:
            return _normalized(p.embedding)
        if p.searchable not in self._vector_cache:
            self._prepare([p])
        return self._vector_cache[p.searchable]

    def _similarity(self, text: str, passage: Passage) -> float:
        if self.embedder is None:
            return _query_coverage(text, passage.searchable)
        if text not in self._query_vectors:
            self._query_vectors[text] = self._encode_many([text])[0]
        return _cosine_positive(self._query_vectors[text], self._passage_vector(passage))

    def _passage_similarity(self, a: Passage, b: Passage) -> float:
        if self.embedder is None:
            return _jaccard(a.searchable, b.searchable)
        return _cosine_positive(self._passage_vector(a), self._passage_vector(b))

    def _freshness(self, published_at: date | datetime | None) -> float:
        if published_at is None:
            return 0.5
        published = published_at.date() if isinstance(published_at, datetime) else published_at
        today = self.now.date() if isinstance(self.now, datetime) else self.now
        return math.exp(-max(0, (today - published).days) / 365.0)

    def score(self, passage: Passage) -> AttentionScore:
        if not 0 <= passage.source_quality <= 1:
            raise ValueError("source_quality must be between 0 and 1")
        relevance = self._similarity(self.intent, passage)
        gap = max((self._similarity(q, passage) for q in self.unresolved_questions), default=0.0)
        terms = _tokens(passage.searchable)
        domain_fit = len(terms & self.domain_terms) / len(self.domain_terms) if self.domain_terms else 0.5
        freshness = self._freshness(passage.published_at)
        # Unverified hypotheses cannot become accepted evidence, but can still
        # prevent repeatedly investigating near-identical findings.
        accepted = [d.passage for d in self.state.accepted]
        known = accepted + [d.passage for d in self.state.investigate]
        redundancy = max((self._passage_similarity(item, passage) for item in known), default=0.0)
        novelty = 1.0 - redundancy
        source_value = passage.source_quality  # provider count != corroboration
        attention = (0.45 * relevance + 0.25 * gap + 0.10 * domain_fit
                     + 0.05 * freshness + 0.15 * source_value)
        return AttentionScore(relevance, gap, domain_fit, freshness, novelty,
                              redundancy, source_value, attention)

    def decide(self, passage: Passage, *, remaining_investigations: int | None = None) -> FocusDecision:
        score = self.score(passage)
        # Hypothesis relevance is a possible bridge for lexically novel sources.
        intent_connected = score.relevance >= self.intent_floor or score.graph_gap >= 0.35
        if not intent_connected:
            action, reason = "archive", "weak alignment with original intent and unresolved questions"
        elif score.redundancy >= self.redundancy_threshold:
            action, reason = "archive", "duplicates an existing claim (not independent corroboration)"
        elif (score.novelty >= self.novelty_threshold or passage.source_quality < 0.35) and self.state.accepted:
            if remaining_investigations is None:
                remaining_investigations = self.investigation_budget
            if remaining_investigations > 0:
                action, reason = "investigate", "potentially valuable but requires independent verification"
            else:
                action, reason = "archive", "deferred: exploration budget exhausted"
        else:
            action, reason = "consider", "eligible evidence candidate (not verified truth)"
        return FocusDecision(passage, score, action, reason)

    def rank(self, passages: Iterable[Passage]) -> list[FocusDecision]:
        """Select sequentially; score against updated state after each item."""
        unique: dict[str, Passage] = {}
        for p in passages:
            if not p.text.strip() or p.source_key in self.state.seen_keys:
                continue
            if p.source_key in unique:
                prior = unique[p.source_key]
                merged_providers = tuple(sorted(set(prior.providers) | set(p.providers)))
                unique[p.source_key] = replace(prior, providers=merged_providers)
            else:
                unique[p.source_key] = p
        candidates = list(unique.values())
        self._prepare(candidates)
        candidates.sort(key=lambda p: self.score(p).attention, reverse=True)
        decisions: list[FocusDecision] = []
        investigations_left = self.investigation_budget
        for passage in candidates:
            decision = self.decide(passage, remaining_investigations=investigations_left)
            if decision.action == "investigate":
                investigations_left -= 1
            bucket = {"consider": self.state.accepted,
                      "investigate": self.state.investigate,
                      "archive": self.state.archived}[decision.action]
            bucket.append(decision)
            self.state.seen_keys.add(passage.source_key)
            decisions.append(decision)
        new_information = any(d.action in {"consider", "investigate"} for d in decisions)
        self.state.stagnant_batches = 0 if new_information else self.state.stagnant_batches + 1
        return decisions

    def record_search_call(self) -> None:
        self.state.search_calls += 1

    def should_stop(self, *, max_search_calls: int = 8, max_stagnant_batches: int = 2) -> bool:
        return (self.state.search_calls >= max_search_calls or
                self.state.stagnant_batches >= max_stagnant_batches)

    def evidence_packet(self, *, max_items: int = 8) -> list[dict]:
        """Compact selected candidates, with provenance and no truth guarantee."""
        return [{"id": d.passage.id, "title": d.passage.title,
                 "text": d.passage.text, "url": d.passage.url,
                 "providers": list(d.passage.providers),
                 "relevance": round(d.score.relevance, 3)}
                for d in sorted(self.state.accepted,
                                key=lambda d: d.score.attention, reverse=True)[:max_items]]
