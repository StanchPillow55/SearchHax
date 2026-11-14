"""Tavily adapter for targeted investigation.

Telem remains the broad discovery path. This module calls Tavily directly for
a different job: search for snippets, then extract only the pages worth reading.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, replace
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from dotenv import load_dotenv

QUERY_MAX_CHARS = 400
SEARCH_RESULT_LIMIT = 20
EXTRACT_URL_LIMIT = 20
DEFAULT_SCORE_THRESHOLD = 0.5
SEARCH_DEPTHS = frozenset({"ultra-fast", "fast", "basic", "advanced"})
EXTRACT_DEPTHS = frozenset({"basic", "advanced"})


@dataclass(frozen=True)
class Source:
    """One normalized web source from Tavily."""

    url: str
    canonical_url: str
    title: str
    snippet: str
    score: float | None
    provider: str = "tavily"
    content: str | None = None


def canonical_url(url: str) -> str:
    """Drop the fragment and trailing slash so the same page dedupes."""

    parts = urlsplit(url.strip())
    if not parts.scheme or not parts.netloc:
        return url.split("#", 1)[0].rstrip("/")
    path = parts.path.rstrip("/")
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, parts.query, ""))


def _bound_query(query: str) -> str:
    text = " ".join(query.split())
    if not text:
        raise ValueError("query must not be empty")
    return text[:QUERY_MAX_CHARS]


def _clamp_int(value: int, low: int, high: int, name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError(f"{name} must be an integer")
    return max(low, min(high, value))


def _score(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _dedupe(sources: list[Source]) -> list[Source]:
    seen: set[str] = set()
    kept: list[Source] = []
    for source in sources:
        key = source.canonical_url
        if not key or key in seen:
            continue
        seen.add(key)
        kept.append(source)
    return kept


def _unique_urls(urls: list[str], limit: int) -> list[str]:
    seen: set[str] = set()
    kept: list[str] = []
    for url in urls:
        if not url or not str(url).strip():
            continue
        key = canonical_url(str(url))
        if key in seen:
            continue
        seen.add(key)
        kept.append(str(url).strip())
        if len(kept) >= limit:
            break
    return kept


def _result_url(item: Any) -> str:
    if isinstance(item, str):
        return item
    if isinstance(item, dict):
        return str(item.get("url") or "")
    return ""


class TavilyRetrieval:
    """Search and extract through the official Tavily Python SDK.

    Pass a client in tests. Otherwise the client uses ``TAVILY_API_KEY`` from
    the environment or the gitignored project ``.env``. With no key, search and
    extract run in Tavily's rate-limited keyless mode.
    """

    def __init__(self, client: Any | None = None, *, api_key: str | None = None) -> None:
        self._client = client
        self._api_key = api_key

    def search(
        self,
        query: str,
        *,
        max_results: int = 5,
        search_depth: str = "advanced",
        topic: str = "general",
        include_domains: list[str] | None = None,
        exclude_domains: list[str] | None = None,
        time_range: str | None = None,
    ) -> list[Source]:
        """Return ranked snippets. Full page text is left to ``extract``."""

        if search_depth not in SEARCH_DEPTHS:
            raise ValueError(f"search_depth must be one of {sorted(SEARCH_DEPTHS)}")
        bounded = _bound_query(query)
        limit = _clamp_int(max_results, 1, SEARCH_RESULT_LIMIT, "max_results")
        kwargs: dict[str, Any] = {
            "max_results": limit,
            "search_depth": search_depth,
            "topic": topic,
            "include_answer": False,
            "include_raw_content": False,
        }
        if include_domains:
            kwargs["include_domains"] = include_domains
        if exclude_domains:
            kwargs["exclude_domains"] = exclude_domains
        if time_range:
            kwargs["time_range"] = time_range

        response = self.client.search(bounded, **kwargs)
        sources: list[Source] = []
        for item in response.get("results") or []:
            url = str(item.get("url") or "").strip()
            if not url:
                continue
            sources.append(
                Source(
                    url=url,
                    canonical_url=canonical_url(url),
                    title=str(item.get("title") or ""),
                    snippet=str(item.get("content") or ""),
                    score=_score(item.get("score")),
                )
            )
        return _dedupe(sources)

    def extract(
        self,
        urls: list[str],
        *,
        query: str | None = None,
        chunks_per_source: int = 3,
        extract_depth: str = "basic",
    ) -> list[Source]:
        """Extract selected pages. A query keeps only the relevant chunks."""

        if extract_depth not in EXTRACT_DEPTHS:
            raise ValueError(f"extract_depth must be one of {sorted(EXTRACT_DEPTHS)}")
        selected = _unique_urls(urls, EXTRACT_URL_LIMIT)
        if not selected:
            return []

        kwargs: dict[str, Any] = {"extract_depth": extract_depth, "format": "markdown"}
        focus = _bound_query(query) if query and query.strip() else None
        if focus:
            kwargs["query"] = focus
            kwargs["chunks_per_source"] = _clamp_int(chunks_per_source, 1, 5, "chunks_per_source")

        response = self.client.extract(selected, **kwargs)
        if extract_depth == "basic":
            failed = [
                url
                for url in (_result_url(item) for item in response.get("failed_results") or [])
                if url
            ]
            if failed:
                retry = self.client.extract(failed, **{**kwargs, "extract_depth": "advanced"})
                response = {
                    "results": [*(response.get("results") or []), *(retry.get("results") or [])],
                    "failed_results": retry.get("failed_results") or [],
                }

        sources: list[Source] = []
        for item in response.get("results") or []:
            url = str(item.get("url") or "").strip()
            if not url:
                continue
            content = item.get("raw_content")
            sources.append(
                Source(
                    url=url,
                    canonical_url=canonical_url(url),
                    title=str(item.get("title") or ""),
                    snippet="",
                    score=None,
                    content=str(content) if content else None,
                )
            )
        return _dedupe(sources)

    def investigate(
        self,
        query: str,
        *,
        max_results: int = 5,
        search_depth: str = "advanced",
        score_threshold: float = DEFAULT_SCORE_THRESHOLD,
        chunks_per_source: int = 3,
    ) -> list[Source]:
        """Search, then extract pages whose relevance score clears the threshold."""

        found = self.search(query, max_results=max_results, search_depth=search_depth)
        chosen = [source for source in found if source.score is not None and source.score > score_threshold]
        if not chosen:
            return found

        extracted = self.extract(
            [source.url for source in chosen],
            query=query,
            chunks_per_source=chunks_per_source,
        )
        by_url = {source.canonical_url: source for source in extracted}
        merged: list[Source] = []
        for source in chosen:
            detail = by_url.get(source.canonical_url)
            if detail and detail.content:
                merged.append(replace(source, content=detail.content))
            else:
                merged.append(source)
        return merged

    @property
    def client(self) -> Any:
        if self._client is None:
            self._client = build_client(self._api_key)
        return self._client


def build_client(api_key: str | None = None) -> Any:
    """Create a Tavily SDK client from an explicit key or ``TAVILY_API_KEY``.

    An empty key uses keyless search and extract. Crawl, map, and research are
    not part of this adapter.
    """

    load_dotenv()
    key = (api_key or os.environ.get("TAVILY_API_KEY") or "").strip()
    from tavily import TavilyClient

    if not key:
        return TavilyClient()
    return TavilyClient(api_key=key)
