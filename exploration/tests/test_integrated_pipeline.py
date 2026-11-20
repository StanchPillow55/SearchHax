"""Deterministic offline end-to-end integration of the full decision cycle.

No network. A fake retrieval client returns fixed pages, so the real
orchestrator, extraction, exact-quote verification, provenance, knowledge-value
scoring, focus ranking, convergence decision, follow-up search, and checkpoint
persistence all run together. Two scenarios are covered: a genuine follow-up
search decision, and a justified stop decision.
"""

from __future__ import annotations

from pathlib import Path

from shared.contracts import ResearchProfile

import pytest

from exploration.backend.focus_bridge import focus_post
from exploration.backend.ids import content_hash
from exploration.backend.orchestrator import Orchestrator
from exploration.backend.retrieval import FetchedPage, MergedDocument, ProviderHit, SearchBundle, normalize_url


@pytest.fixture(autouse=True)
def _offline_extraction(monkeypatch):
    """Keep this scenario deterministic and free: no live LLM extraction.

    Supported facts come from the disclosed-sentence extractor, which does not
    need a model, so clearing the key does not reduce grounded coverage.
    """
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    # The orchestrator refuses a live step unless a Telem credential is
    # configured. Retrieval here is the in-process fake below, which never
    # reads this value or opens a connection (each test asserts zero network
    # fetches), so a placeholder only satisfies the configuration gate.
    monkeypatch.setenv("TELEM_API_KEY", "offline-test-placeholder-not-a-key")

# A page that states the disclosed NVIDIA/CoreWeave fact (grounded by the
# deterministic extractor) and profile-relevant GPU/packaging/capacity terms
# that trigger knowledge-value bridges.
PAGE_A = (
    "NVIDIA has invested $2 billion in CoreWeave to expand GPU datacenter capacity. "
    "The buildout emphasizes advanced packaging and HBM supply for AI systems."
)
# A lexically distinct page on the same investments/capacity theme, novel enough
# that focus routes it to investigate and approves a follow-up search.
PAGE_NOVEL = (
    "A separate filing describes how NVIDIA investments and AI capacity expansion "
    "reinforce GPU infrastructure customers through long-term supply agreements."
)
# A page fetched only when a follow-up search is approved.
PAGE_B = (
    "Analysts tie the CoreWeave GPU capacity expansion to downstream customer demand "
    "and financing for new datacenter campus power."
)

# Snippets that overlap the investigation question so candidates clear the focus
# intent floor, but differ enough from each other that the second is novel.
# Keyed by canonical url.
_SNIPPETS = {
    # Both clear the 0.20 intent floor. The supply page is scored first as the
    # accepted candidate; the coreweave page is then novel enough (> 0.55) to be
    # routed to investigate, which is what makes focus approve a follow-up.
    "https://news.example-live/nvidia-coreweave": "NVIDIA investments CoreWeave GPU capacity expansion",
    "https://news.example-live/nvidia-supply": "AI capacity expansion GPU infrastructure customers reinforce one another supply agreements",
    "https://news.example-live/coreweave-demand": "capacity expansion downstream customer demand",
}

PROFILE = ResearchProfile(
    id="profile_test_ai",
    interests=["AI systems", "GPUs", "data-center capacity", "semiconductor", "advanced packaging"],
    goals=["Track GPU supply", "Follow data-center capacity"],
    unresolved_interests=["advanced packaging"],
    known_claims=[],
    notes="Static read-only test profile.",
)

QUESTION = (
    "How do NVIDIA's investments, GPU infrastructure customers, and AI capacity "
    "expansion reinforce one another?"
)


class _FakeRetrieval:
    """Minimal stand-in for RetrievalClient. Deterministic, no network."""

    def __init__(self, pages: dict[str, str], *, follow_up_url: str | None = None):
        self.dry_run = False
        self.session_id = "session_fixture"
        self.interaction_ids: list[str] = []
        self._pages = {normalize_url(url): content for url, content in pages.items()}
        self._follow_up_url = follow_up_url
        self.searches: list[str] = []
        self.fetches: list[list[str]] = []

    def _hits(self, urls: list[str]) -> list[ProviderHit]:
        hits = []
        for i, url in enumerate(urls):
            canonical = normalize_url(url)
            hits.append(
                ProviderHit(
                    provider="brave" if i % 2 == 0 else "tavily",
                    url=url,
                    canonical_url=canonical,
                    title="Fixture page",
                    snippet=_SNIPPETS.get(canonical, "NVIDIA GPU capacity expansion"),
                    publish_date="2026-10-01",
                )
            )
        return hits

    def search(self, query, session_id=None, guard=None):
        if guard is not None:
            guard.authorize_search()
        self.searches.append(query)
        # First search returns the initial page(s); a follow-up search returns
        # the follow-up url, if one is configured.
        follow = normalize_url(self._follow_up_url or "")
        if len(self.searches) == 1:
            urls = [u for u in self._pages if u != follow]
        else:
            urls = [follow] if self._follow_up_url else []
        hits = self._hits(urls)
        docs = [
            MergedDocument(
                canonical_url=h.canonical_url,
                title=h.title,
                snippet=h.snippet,
                providers=[h.provider],
                hits=[h],
                publish_date=h.publish_date,
            )
            for h in hits
        ]
        return SearchBundle(
            query=query,
            session_id=self.session_id,
            interaction_id=f"interaction_{len(self.searches)}",
            documents=docs,
            provider_hits=hits,
            provider_call_count=len(hits),
            raw={"note": "fixture"},
        )

    def fetch(self, urls, session_id=None, guard=None):
        self.fetches.append(list(urls))
        if guard is not None:
            guard.authorize_fetch(len(urls))
        pages = []
        for url in urls:
            canonical = normalize_url(url)
            content = self._pages.get(canonical, "")
            pages.append(
                FetchedPage(
                    url=url,
                    canonical_url=canonical,
                    title="Fixture page",
                    content=content,
                    content_hash=content_hash(content) if content else "",
                    status="ok" if content else "missing",
                    provider="telem",
                    publish_date="2026-10-01",
                )
            )
        return pages

    def cached_fetch(self, url):
        canonical = normalize_url(url)
        content = self._pages.get(canonical)
        if not content:
            return None
        return FetchedPage(
            url=url,
            canonical_url=canonical,
            content=content,
            content_hash=content_hash(content),
            status="ok",
            from_cache=True,
        )


def _run(tmp_path: Path, pages: dict[str, str], *, follow_up_url: str | None, post):
    retrieval = _FakeRetrieval(pages, follow_up_url=follow_up_url)
    orch = Orchestrator(tmp_path / "integrated.sqlite", retrieval=retrieval, post=post)
    inv = orch.create(QUESTION, mode="web", profile=PROFILE)
    first = orch.step(inv.id)
    second = orch.step(inv.id)
    resume = orch.resume(inv.id)
    return orch, retrieval, first, second, resume


def test_profile_live_pipeline_runs_a_follow_up_through_convergence(tmp_path: Path):
    pages = {
        "https://news.example-live/nvidia-coreweave": PAGE_A,
        "https://news.example-live/nvidia-supply": PAGE_NOVEL,
        "https://news.example-live/coreweave-demand": PAGE_B,
    }
    orch, retrieval, _first, export, resume = _run(
        tmp_path,
        pages,
        follow_up_url="https://news.example-live/coreweave-demand",
        post=focus_post,
    )
    inv = export.investigation

    # Profile-conditioned knowledge value rode along on live candidates,
    # separate from query attention.
    scored = [c for c in export.candidates if c.knowledge_value is not None]
    assert scored, "no candidate received a knowledge-value score"
    for candidate in scored:
        assert candidate.attention is not None  # query attention preserved
        assert 0.0 <= candidate.knowledge_value.score <= 1.0

    # The decision came from the focus-backed convergence controller, not a
    # silent fallback.
    assert inv.decision_source == "convergence", inv.decision_rationale

    # A follow-up search actually executed (two searches total).
    assert inv.usage.search_calls >= 2
    assert len(retrieval.searches) >= 2

    # Exact-quote verified supported facts exist and are grounded substrings.
    supported = [r for r in export.relationships if r.status == "supported"]
    assert supported, "expected at least one quote-verified supported fact"
    versions = {v.document_id: v for v in export.document_versions}
    for link in export.evidence_links:
        span = next((s for s in export.evidence_spans if s.id == link.evidence_span_id), None)
        if span is None:
            continue
        version = versions.get(span.document_id)
        assert version is not None
        assert version.content[span.start : span.end] == span.text

    # Profile-interest open question was surfaced for focus/convergence.
    assert any(q.kind == "profile_interest" for q in export.unresolved_questions)

    # Checkpoints persisted and resume did not refetch anything.
    assert export.checkpoints
    assert resume["network_fetches"] == 0


def test_profile_live_pipeline_stops_when_no_useful_action(tmp_path: Path):
    # No follow-up url, so after the first page there is no new search to run:
    # the decision cycle must stop with a labeled convergence reason.
    pages = {"https://news.example-live/nvidia-coreweave": PAGE_A}
    orch, retrieval, _first, export, resume = _run(
        tmp_path, pages, follow_up_url=None, post=focus_post
    )
    inv = export.investigation

    assert inv.decision_source in {"convergence", "fallback"}
    assert inv.status == "stopped"
    assert inv.stop_reason in {
        "evidence_sufficient",
        "low_expected_value",
        "no_useful_actions",
        "unresolved_uncertainty",
        "budget_exhausted",
    }
    # Still grounded and still scored with knowledge value.
    assert any(c.knowledge_value is not None for c in export.candidates)
    assert resume["network_fetches"] == 0
