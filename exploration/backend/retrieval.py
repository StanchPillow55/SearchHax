"""Telem-first search and fetch with disk cache, dry-run replay, and hard limits.

Default providers are brave and tavily, tier is default, and each provider is
asked for 3 results. One fetch call receives at most 5 URLs. Retries are
limited to transient 429/5xx and connection failures. Tavily extract is used
only when a Telem fetch returns empty content and TAVILY_API_KEY is set.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from pydantic import BaseModel, ConfigDict, Field

from exploration.backend.budget import BudgetExceededError, BudgetGuard
from exploration.backend.config import (
    DEFAULT_PROVIDERS,
    DEFAULT_TIER,
    HTTP_TIMEOUT_SECONDS,
    RESULTS_PER_PROVIDER,
    SEARCH_RETRIES,
    default_cache_dir,
    env_flag,
    replay_fixture_path,
    tavily_api_key,
    telem_base_url,
    telem_configured,
)
from exploration.backend.ids import content_hash, stable_id

TRANSIENT_STATUS = {429, 500, 502, 503, 504}
TRANSIENT_TYPES = {
    "TelemConnectionError",
    "TelemTimeoutError",
    "ConnectError",
    "ReadTimeout",
    "ConnectTimeout",
    "RemoteProtocolError",
    "TimeoutException",
}


class ProviderHit(BaseModel):
    model_config = ConfigDict(extra="ignore")
    provider: str
    url: str
    canonical_url: str
    title: str = ""
    snippet: str = ""
    publish_date: str | None = None
    rank: int | None = None


class MergedDocument(BaseModel):
    model_config = ConfigDict(extra="ignore")
    canonical_url: str
    title: str = ""
    snippet: str = ""
    providers: list[str] = Field(default_factory=list)
    hits: list[ProviderHit] = Field(default_factory=list)
    publish_date: str | None = None


class SearchBundle(BaseModel):
    model_config = ConfigDict(extra="ignore")
    query: str
    session_id: str | None = None
    interaction_id: str | None = None
    documents: list[MergedDocument] = Field(default_factory=list)
    provider_hits: list[ProviderHit] = Field(default_factory=list)
    provider_call_count: int = 0
    provider_errors: list[str] = Field(default_factory=list)
    from_cache: bool = False
    dry_run: bool = False
    raw: dict[str, Any] = Field(default_factory=dict)


class FetchedPage(BaseModel):
    model_config = ConfigDict(extra="ignore")
    url: str
    canonical_url: str
    title: str = ""
    content: str = ""
    content_hash: str = ""
    status: str = ""
    provider: str = "telem"
    from_cache: bool = False
    error: str | None = None
    publish_date: str | None = None


@dataclass
class RetrievalClient:
    cache_dir: Any = None
    dry_run: bool | None = None
    providers: tuple[str, ...] = DEFAULT_PROVIDERS
    tier: str = DEFAULT_TIER
    num_results: int = RESULTS_PER_PROVIDER
    timeout: float = HTTP_TIMEOUT_SECONDS
    max_retries: int = SEARCH_RETRIES
    search_fn: Callable[..., Any] | None = None
    fetch_fn: Callable[..., Any] | None = None
    tavily_extract_fn: Callable[[str], str] | None = None
    sleeper: Callable[[float], None] = field(default=time.sleep)
    session_id: str | None = None
    interaction_ids: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.cache_dir is None:
            self.cache_dir = default_cache_dir()
        self.cache_dir = self.cache_dir if hasattr(self.cache_dir, "joinpath") else __import__("pathlib").Path(self.cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        if self.dry_run is None:
            self.dry_run = env_flag("DRY_RUN")
        if self.tavily_extract_fn is None and tavily_api_key() and not self.dry_run:
            self.tavily_extract_fn = _default_tavily_extract

    def search(
        self,
        query: str,
        session_id: str | None = None,
        guard: BudgetGuard | None = None,
    ) -> SearchBundle:
        if guard is not None:
            guard.authorize_search()
        active_session = session_id if session_id is not None else self.session_id
        cache_key = _search_cache_key(query, self.providers, self.num_results, self.tier)
        if self.dry_run:
            cached = self._read_json(self.cache_dir / "search" / f"{cache_key}.json")
            if cached is not None:
                bundle = SearchBundle.model_validate(cached)
                bundle.from_cache = True
                bundle.dry_run = True
                self._remember_session(bundle)
                return bundle
            synthetic = _synthetic_for_query(query)
            if synthetic is not None:
                synthetic.dry_run = True
                synthetic.from_cache = False
                self._remember_session(synthetic)
                return synthetic
            return SearchBundle(query=query, dry_run=True, raw={"note": "dry_run_cache_miss"})

        def attempt() -> SearchBundle:
            if self.search_fn is not None:
                payload = self.search_fn(query, active_session)
                return _bundle_from_mapping(query, payload)
            return _sdk_search(
                query,
                session_id=active_session,
                providers=list(self.providers),
                tier=self.tier,
                num_results=self.num_results,
                timeout=self.timeout,
            )

        bundle = call_with_retries(attempt, sleeper=self.sleeper, max_retries=self.max_retries)
        self._remember_session(bundle)
        self._write_json(self.cache_dir / "search" / f"{cache_key}.json", bundle.model_dump(mode="json"))
        return bundle

    def fetch(self, urls: list[str], session_id: str | None = None, guard: BudgetGuard | None = None) -> list[FetchedPage]:
        if len(urls) > 5:
            raise BudgetExceededError("fetch_batch")
        ordered: list[FetchedPage | None] = []
        missing: list[str] = []
        missing_at: list[int] = []
        for url in urls:
            canonical = normalize_url(url)
            cached = self._read_json(self._fetch_path(canonical))
            if cached is not None and cached.get("content"):
                page = FetchedPage.model_validate(cached)
                page.from_cache = True
                ordered.append(page)
            else:
                ordered.append(None)
                missing.append(url)
                missing_at.append(len(ordered) - 1)
        if not missing:
            return [page for page in ordered if page is not None]
        if self.dry_run:
            for index, url in zip(missing_at, missing, strict=True):
                ordered[index] = FetchedPage(
                    url=url,
                    canonical_url=normalize_url(url),
                    status="dry_run_miss",
                    provider="cache",
                    error="dry_run_miss",
                )
            return [page for page in ordered if page is not None]
        if guard is not None:
            guard.authorize_fetch(len(missing))
        active_session = session_id if session_id is not None else self.session_id
        fetched = self._fetch_missing(missing, active_session)
        by_url = {normalize_url(page.url): page for page in fetched}
        by_url.update({page.canonical_url: page for page in fetched})
        empty = 0
        for index, url in zip(missing_at, missing, strict=True):
            page = by_url.get(normalize_url(url))
            if page is None:
                page = FetchedPage(url=url, canonical_url=normalize_url(url), status="missing", error="missing")
            if not page.content.strip() and self.tavily_extract_fn is not None:
                extracted = self.tavily_extract_fn(page.canonical_url)
                if extracted:
                    page.content = extracted
                    page.content_hash = content_hash(extracted)
                    page.provider = "tavily_extract"
                    page.status = page.status or "extracted"
            if page.content and not page.content_hash:
                page.content_hash = content_hash(page.content)
            self._write_json(self._fetch_path(page.canonical_url), page.model_dump(mode="json"))
            requested = normalize_url(url)
            if requested != page.canonical_url:
                # Also cache under the requested URL so a later fetch of the
                # same search hit is served from cache.
                self._write_json(self._fetch_path(requested), page.model_dump(mode="json"))
            if not page.content.strip():
                empty += 1
            ordered[index] = page
        if guard is not None and empty:
            # A fetch that returned no body does not spend a fetched-URL slot.
            guard.release_fetch(empty)
        return [page for page in ordered if page is not None]

    def cached_fetch(self, url: str) -> FetchedPage | None:
        cached = self._read_json(self._fetch_path(normalize_url(url)))
        if cached is None:
            return None
        page = FetchedPage.model_validate(cached)
        page.from_cache = True
        return page

    def _fetch_missing(self, urls: list[str], session_id: str | None) -> list[FetchedPage]:
        def attempt() -> list[FetchedPage]:
            if self.fetch_fn is not None:
                payload = self.fetch_fn(urls, session_id)
                return _pages_from_mapping(payload)
            return _sdk_fetch(urls, session_id=session_id, timeout=self.timeout)

        return call_with_retries(attempt, sleeper=self.sleeper, max_retries=self.max_retries)

    def _fetch_path(self, canonical_url: str):
        digest = stable_id("url", canonical_url).split("_", 1)[1]
        return self.cache_dir / "fetch" / f"{digest}.json"

    def _remember_session(self, bundle: SearchBundle) -> None:
        if bundle.session_id:
            self.session_id = bundle.session_id
        if bundle.interaction_id and bundle.interaction_id not in self.interaction_ids:
            self.interaction_ids.append(bundle.interaction_id)

    def _read_json(self, path) -> dict[str, Any] | None:
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def _write_json(self, path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def normalize_url(url: str) -> str:
    """Strip the fragment, drop a trailing slash on non-root paths, and lowercase the host."""
    raw = url.strip()
    parts = urlsplit(raw)
    if not parts.scheme or not parts.hostname:
        return raw.split("#", 1)[0].rstrip("/") or raw
    host = parts.hostname.lower()
    netloc = f"{host}:{parts.port}" if parts.port else host
    path = parts.path or "/"
    if path != "/":
        path = path.rstrip("/")
    return urlunsplit((parts.scheme.lower(), netloc, path, parts.query, ""))


def merge_provider_hits(hits: list[ProviderHit]) -> list[MergedDocument]:
    """One canonical URL is one document, even when several providers returned it.

    Provider identity is preserved on the document and on the original hits.
    Two providers finding the same URL are not two independent sources.
    """
    grouped: dict[str, MergedDocument] = {}
    order: list[str] = []
    for hit in hits:
        key = hit.canonical_url
        if key not in grouped:
            grouped[key] = MergedDocument(
                canonical_url=key,
                title=hit.title,
                snippet=hit.snippet,
                providers=[hit.provider] if hit.provider else [],
                hits=[hit],
                publish_date=hit.publish_date,
            )
            order.append(key)
            continue
        document = grouped[key]
        document.hits.append(hit)
        if hit.provider and hit.provider not in document.providers:
            document.providers.append(hit.provider)
        if not document.title and hit.title:
            document.title = hit.title
        if not document.snippet and hit.snippet:
            document.snippet = hit.snippet
        if not document.publish_date and hit.publish_date:
            document.publish_date = hit.publish_date
    return [grouped[key] for key in order]


def independent_source_count(documents: list[MergedDocument]) -> int:
    return len({document.canonical_url for document in documents})


def call_with_retries(fn: Callable[[], Any], *, sleeper: Callable[[float], None], max_retries: int) -> Any:
    attempt = 0
    while True:
        try:
            return fn()
        except Exception as exc:
            if not _is_transient(exc) or attempt >= max_retries:
                raise
            sleeper(min(2.0, 0.25 * (2**attempt)))
            attempt += 1


def _is_transient(exc: Exception) -> bool:
    status = getattr(exc, "status_code", None)
    if status in TRANSIENT_STATUS:
        return True
    return type(exc).__name__ in TRANSIENT_TYPES


def _search_cache_key(query: str, providers: tuple[str, ...], num_results: int, tier: str) -> str:
    raw = json.dumps({"q": query, "p": list(providers), "n": num_results, "t": tier}, sort_keys=True)
    return content_hash(raw)[:32]


def _snippet_from_result(result: Any) -> str:
    if isinstance(result, dict):
        summary = result.get("summary") or ""
        excerpt = result.get("excerpt") or result.get("snippet") or ""
    else:
        summary = getattr(result, "summary", None) or ""
        excerpt = getattr(result, "excerpt", None) or ""
    if isinstance(excerpt, list):
        excerpt = " ".join(str(part) for part in excerpt if part)
    return str(summary or excerpt or "").strip()


def _hit_from_mapping(provider: str, row: dict[str, Any]) -> ProviderHit | None:
    url = str(row.get("url") or "").strip()
    if not url:
        return None
    publish = row.get("publish_date")
    return ProviderHit(
        provider=str(row.get("provider") or provider or "unknown"),
        url=url,
        canonical_url=normalize_url(url),
        title=str(row.get("title") or ""),
        snippet=_snippet_from_result(row),
        publish_date=str(publish) if publish else None,
        rank=row.get("rank") if isinstance(row.get("rank"), int) else None,
    )


def _bundle_from_mapping(query: str, payload: Any) -> SearchBundle:
    if isinstance(payload, SearchBundle):
        return payload
    data = payload if isinstance(payload, dict) else {}
    hits: list[ProviderHit] = []
    errors: list[str] = []
    runs = data.get("by_provider") or data.get("provider_runs") or []
    if runs:
        for run in runs:
            if not isinstance(run, dict):
                run = run.model_dump(mode="python") if hasattr(run, "model_dump") else {}
            provider = str(run.get("provider") or "unknown")
            if run.get("error"):
                errors.append(f"{provider}: {run.get('status') or 'error'}")
            for row in run.get("results") or []:
                if not isinstance(row, dict):
                    row = row.model_dump(mode="python") if hasattr(row, "model_dump") else {}
                hit = _hit_from_mapping(provider, row)
                if hit:
                    hits.append(hit)
    else:
        for row in data.get("results") or []:
            if not isinstance(row, dict):
                row = row.model_dump(mode="python") if hasattr(row, "model_dump") else {}
            hit = _hit_from_mapping(str(row.get("provider") or "unknown"), row)
            if hit:
                hits.append(hit)
    provider_count = len(runs) if runs else len({hit.provider for hit in hits})
    return SearchBundle(
        query=query,
        session_id=(str(data.get("session_id")) if data.get("session_id") else None),
        interaction_id=(str(data.get("interaction_id")) if data.get("interaction_id") else None),
        documents=merge_provider_hits(hits),
        provider_hits=hits,
        provider_call_count=provider_count,
        provider_errors=errors,
        raw={
            "session_id": data.get("session_id"),
            "interaction_id": data.get("interaction_id"),
            "provider_runs": [
                {
                    "provider": (run.get("provider") if isinstance(run, dict) else getattr(run, "provider", None)),
                    "status": (run.get("status") if isinstance(run, dict) else getattr(run, "status", None)),
                }
                for run in runs
            ],
        },
    )


def _pages_from_mapping(payload: Any) -> list[FetchedPage]:
    if isinstance(payload, list):
        rows = payload
    else:
        rows = (payload or {}).get("results") or []
    pages: list[FetchedPage] = []
    for row in rows:
        if not isinstance(row, dict):
            row = row.model_dump(mode="python") if hasattr(row, "model_dump") else {}
        url = str(row.get("url") or "")
        content = str(row.get("content") or "")
        pages.append(
            FetchedPage(
                url=url,
                canonical_url=normalize_url(str(row.get("canonical_url") or url)),
                title=str(row.get("title") or ""),
                content=content,
                content_hash=content_hash(content) if content else "",
                status=str(row.get("status") or ""),
                provider=str(row.get("provider") or "telem"),
                error=str(row.get("error")) if row.get("error") else None,
                publish_date=str(row.get("publish_date")) if row.get("publish_date") else None,
            )
        )
    return pages


def _sdk_search(
    query: str,
    *,
    session_id: str | None,
    providers: list[str],
    tier: str,
    num_results: int,
    timeout: float,
) -> SearchBundle:
    client = _telem_client(timeout)
    try:
        response = client.search(
            query,
            tier=tier,
            providers_include=providers,
            num_results=num_results,
            include_full_content=False,
            session=session_id,
        )
    finally:
        client.close()
    hits: list[ProviderHit] = []
    errors: list[str] = []
    for run in response.by_provider:
        if run.error:
            errors.append(f"{run.provider}: {run.status}")
        for result in run.results:
            if not result.url:
                continue
            hits.append(
                ProviderHit(
                    provider=result.provider or run.provider or "unknown",
                    url=result.url,
                    canonical_url=normalize_url(result.url),
                    title=result.title or "",
                    snippet=_snippet_from_result(result),
                    publish_date=result.publish_date,
                    rank=result.rank,
                )
            )
    raw_runs = []
    for run in response.by_provider:
        raw_runs.append(
            {
                "provider": run.provider,
                "status": run.status,
                "error": run.error,
                "results": [hit.model_dump(mode="json") for hit in hits if hit.provider == run.provider],
            }
        )
    return SearchBundle(
        query=query,
        session_id=response.session_id or None,
        interaction_id=response.interaction_id or None,
        documents=merge_provider_hits(hits),
        provider_hits=hits,
        provider_call_count=len(response.by_provider),
        provider_errors=errors,
        raw={"provider_runs": raw_runs, "status": response.status},
    )


def _sdk_fetch(urls: list[str], *, session_id: str | None, timeout: float) -> list[FetchedPage]:
    client = _telem_client(timeout)
    try:
        response = client.fetch(urls, session=session_id)
    finally:
        client.close()
    if response.session_id:
        # The caller stores search session ids. Fetch interaction ids are returned on pages via status.
        pass
    pages: list[FetchedPage] = []
    for result in response.results:
        content = result.content or ""
        pages.append(
            FetchedPage(
                url=result.url,
                canonical_url=normalize_url(result.canonical_url or result.url),
                title=result.title or "",
                content=content,
                content_hash=result.content_sha256 or (content_hash(content) if content else ""),
                status=result.status or "",
                provider=result.provider or "telem",
                error=json.dumps(result.error) if result.error else None,
                publish_date=_sdk_publish_date(result),
            )
        )
    return pages


def _sdk_publish_date(result: Any) -> str | None:
    value = getattr(result, "publish_date", None)
    if not value:
        metadata = getattr(result, "provider_metadata", None)
        if isinstance(metadata, dict):
            value = metadata.get("publish_date") or metadata.get("published_date")
    return str(value) if value else None


def _telem_client(timeout: float):
    try:
        from telem import Telem
    except Exception as exc:  # pragma: no cover - exercised only when the SDK is broken
        raise RuntimeError(f"telem-sdk import failed: {type(exc).__name__}") from exc
    return Telem(
        base_url=telem_base_url(),
        timeout=timeout,
        default_tier=DEFAULT_TIER,
        default_providers_include=list(DEFAULT_PROVIDERS),
    )


def _default_tavily_extract(url: str) -> str:
    key = tavily_api_key()
    if not key:
        return ""
    from tavily import TavilyClient

    client = TavilyClient(api_key=key)
    payload = client.extract(urls=[url], timeout=HTTP_TIMEOUT_SECONDS)
    for row in payload.get("results") or []:
        if not isinstance(row, dict):
            continue
        text = row.get("raw_content") or row.get("content") or row.get("text") or ""
        if str(text).strip():
            return str(text)
    return ""


def _synthetic_for_query(query: str) -> SearchBundle | None:
    path = replay_fixture_path()
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("query") != query:
        return None
    return _bundle_from_mapping(query, data)


def smoke_status() -> dict[str, Any]:
    """Report whether a live Telem call can run. Does not invent results."""
    report: dict[str, Any] = {
        "ran": False,
        "credentials": "set" if telem_configured() else "missing",
        "blocker": None if telem_configured() else "TELEM_API_KEY missing",
        "sdk_import": "unchecked",
    }
    try:
        import telem  # noqa: F401

        report["sdk_import"] = "ok"
    except Exception as exc:
        report["sdk_import"] = type(exc).__name__
        report["blocker"] = f"telem-sdk import failed: {type(exc).__name__}"
        return report
    return report
