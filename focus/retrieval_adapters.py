"""Optional live search adapters. No network requests occur on import.

Telem response schemas may vary; unknown payloads fail loudly, rather than
silently pretending an API response contained valid results.
"""
from __future__ import annotations
import os
from typing import Any
from urllib.parse import urlsplit
from dataclasses import replace
from focus_attention import Passage, FocusDecision, canonical_url


def _results(payload: Any) -> list[dict]:
    if isinstance(payload, list):
        return [r for r in payload if isinstance(r, dict)]
    if not isinstance(payload, dict):
        raise ValueError('Unexpected search response: expected JSON object/list')
    # Telem returns one result list per provider under preprocessor_runs[].
    # Flatten those runs while retaining the provider provenance.
    runs = payload.get('preprocessor_runs')
    if isinstance(runs, list):
        flattened = []
        for run in runs:
            if not isinstance(run, dict) or not isinstance(run.get('output_payload'), dict):
                continue
            try:
                rows = _results(run['output_payload'])
            except ValueError:
                continue
            provider = run.get('preprocessor_name')
            for row in rows:
                enriched = dict(row)
                providers = enriched.get('providers')
                names = list(providers) if isinstance(providers, list) else []
                if provider:
                    names.append(str(provider))
                enriched['providers'] = sorted(set(names))
                flattened.append(enriched)
        if flattened:
            return flattened
    for key in ('results', 'search_results', 'items'):
        if isinstance(payload.get(key), list):
            return _results(payload[key])
    for key in ('data', 'response', 'search'):
        if isinstance(payload.get(key), (list, dict)):
            try:
                return _results(payload[key])
            except ValueError:
                continue
    raise ValueError('No recognized search results in response; inspect provider JSON schema')


def normalize_results(payload: Any, provider: str) -> list[Passage]:
    out = []
    for i, item in enumerate(_results(payload)):
        url = str(item.get('url') or item.get('link') or item.get('href') or '')
        if not url.startswith(('https://', 'http://')):
            continue
        title = str(item.get('title') or '')
        content = str(item.get('content') or item.get('summary') or
                      item.get('snippet') or item.get('description') or title)
        if not content.strip():
            continue
        providers = item.get('providers')
        if isinstance(providers, list):
            names = tuple(sorted(set(str(x) for x in providers) | {provider}))
        else:
            names = (provider,)
        out.append(Passage(id=f'{provider}:{i}:{url}', text=content[:5000],
                           url=url, title=title, providers=names,
                           domain=urlsplit(url).hostname or ''))
    return out


def _fetch_rows(payload: Any) -> list[dict]:
    """Read Telem's one-document-per-URL fetch response."""
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if not isinstance(payload, dict):
        raise ValueError('Unexpected fetch response: expected JSON object/list')
    # Telem's normalized envelope stores fetched documents under each URL's
    # preprocessor run.
    runs = payload.get('preprocessor_runs')
    if isinstance(runs, list):
        rows = []
        for run in runs:
            if not isinstance(run, dict):
                continue
            output = run.get('output_payload')
            if isinstance(output, dict) and isinstance(output.get('fetched_results'), list):
                rows.extend(row for row in output['fetched_results'] if isinstance(row, dict))
        if rows:
            return rows
    for key in ('results', 'documents', 'items'):
        if isinstance(payload.get(key), list):
            return [row for row in payload[key] if isinstance(row, dict)]
    for key in ('data', 'response'):
        if isinstance(payload.get(key), (list, dict)):
            try:
                return _fetch_rows(payload[key])
            except ValueError:
                continue
    raise ValueError('No recognized fetched documents in Telem response')


def telem_fetch(urls: list[str], *, inline_max_chars: int = 12000,
                no_cache: bool = False) -> dict[str, str]:
    """Fetch selected pages through Telem and return content keyed by URL.

    Telem caps a fetch request at five URLs, so larger selections are split
    into batches. Failed individual URLs are skipped so callers can retain the
    original search snippet as a fallback.
    """
    key = os.getenv('TELEM_API_KEY')
    if not key:
        raise RuntimeError('Set TELEM_API_KEY before Telem page fetching')
    if inline_max_chars < 1:
        raise ValueError('inline_max_chars must be positive')
    import requests  # pip install requests
    endpoint = os.getenv('TELEM_FETCH_URL') or os.getenv('TELEM_BASE_URL', 'https://router.telem.ai')
    endpoint = endpoint.rstrip('/')
    if not endpoint.endswith('/v1/fetch'):
        endpoint += '/v1/fetch'
    unique_urls = list(dict.fromkeys(url for url in urls if url.startswith(('http://', 'https://'))))
    fetched: dict[str, str] = {}
    for start in range(0, len(unique_urls), 5):
        batch = unique_urls[start:start + 5]
        payload = {
            'urls': batch,
            'options': {
                'tier': 'default',
                'content_format': 'markdown',
                'inline_content': True,
                'inline_max_chars': inline_max_chars,
            },
        }
        if no_cache:
            payload['options']['no_cache'] = True
        response = requests.post(endpoint,
            headers={'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'},
            json=payload, timeout=90)
        response.raise_for_status()
        for row in _fetch_rows(response.json()):
            # A failed fetch may still carry a body (an error page); it is not
            # page text and must not replace the search snippet.
            status = row.get('status')
            if row.get('error') or (
                    isinstance(status, str) and status.strip().lower()
                    not in {'ok', 'success', 'succeeded', 'completed', 'complete', 'cached'}):
                continue
            content = row.get('content') or row.get('text') or row.get('markdown')
            url = row.get('url') or row.get('canonical_url') or row.get('final_url')
            if isinstance(content, str) and content.strip() and isinstance(url, str):
                fetched[canonical_url(url)] = content[:inline_max_chars]
    return fetched


def hydrate_decisions(decisions: list[FocusDecision], *, max_sources: int = 5,
                      inline_max_chars: int = 12000) -> list[FocusDecision]:
    """Replace selected passages with Telem page text, preserving decisions."""
    selected = [decision for decision in decisions if decision.action == 'consider'][:max_sources]
    if not selected:
        return decisions
    fetched = telem_fetch([decision.passage.url for decision in selected],
                          inline_max_chars=inline_max_chars)
    hydrated = []
    selected_keys = {decision.passage.source_key for decision in selected}
    for decision in decisions:
        if decision.passage.source_key not in selected_keys:
            hydrated.append(decision)
            continue
        content = fetched.get(decision.passage.source_key)
        if content:
            hydrated.append(replace(decision, passage=replace(decision.passage, text=content)))
        else:
            hydrated.append(decision)
    return hydrated


def tavily_search(query: str, max_results: int = 8) -> list[Passage]:
    key = os.getenv('TAVILY_API_KEY')
    if not key:
        raise RuntimeError('Set TAVILY_API_KEY before live Tavily search')
    from tavily import TavilyClient  # pip install tavily-python
    client = TavilyClient(api_key=key)
    payload = client.search(query=query, search_depth='basic',
                            max_results=max_results, include_raw_content=False)
    return normalize_results(payload, 'tavily')


def telem_search(query: str, max_results: int = 8) -> list[Passage]:
    key = os.getenv('TELEM_API_KEY')
    if not key:
        raise RuntimeError('Set TELEM_API_KEY before live Telem search')
    import requests  # pip install requests
    # Accept either the documented base URL (for example
    # https://hack.telem.ai/api) or a complete search endpoint. A base URL
    # responds with 405 when POSTed to directly, so normalize it here.
    endpoint = os.getenv('TELEM_SEARCH_URL') or os.getenv(
        'TELEM_BASE_URL', 'https://router.telem.ai'
    )
    endpoint = endpoint.rstrip('/')
    if not endpoint.endswith('/v1/search'):
        endpoint += '/v1/search'
    response = requests.post(endpoint,
        headers={'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'},
        json={'user_input': {'query': query},
              'search': {'num_results': max_results, 'include_full_content': False}},
        timeout=30)
    response.raise_for_status()
    return normalize_results(response.json(), 'telem')


def search(query: str, provider: str, max_results: int = 8) -> list[Passage]:
    if provider == 'telem':
        return telem_search(query, max_results)
    if provider == 'tavily':
        return tavily_search(query, max_results)
    if provider == 'both':
        # One provider's failure must not discard the other provider's pages.
        # Only when every provider fails is the search itself a failure.
        results = []
        errors: list[Exception] = []
        for func in (telem_search, tavily_search):
            try:
                results.extend(func(query, max_results))
            except Exception as exc:  # noqa: BLE001 - re-raised below if all fail
                errors.append(exc)
        if errors and len(errors) == 2:
            raise errors[0]
        return results
    raise ValueError('provider must be telem, tavily or both')
