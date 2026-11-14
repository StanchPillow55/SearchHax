"""Unit tests for the Tavily retrieval adapter. No network."""

from __future__ import annotations

import pytest

from searchhax.retrieval import (
    QUERY_MAX_CHARS,
    Source,
    TavilyRetrieval,
    build_client,
    canonical_url,
)


class FakeTavily:
    def __init__(self, search_payload=None, extract_payloads=None):
        self.search_calls = []
        self.extract_calls = []
        self.search_payload = search_payload or {"results": []}
        self.extract_payloads = list(extract_payloads or [{"results": [], "failed_results": []}])

    def search(self, query, **kwargs):
        self.search_calls.append((query, kwargs))
        return self.search_payload

    def extract(self, urls, **kwargs):
        self.extract_calls.append((list(urls), kwargs))
        if not self.extract_payloads:
            return {"results": [], "failed_results": []}
        return self.extract_payloads.pop(0)


def test_canonical_url_strips_fragment_slash_and_host_case():
    assert canonical_url("https://Example.com/a/#section") == "https://example.com/a"
    assert canonical_url("https://example.com/a") == "https://example.com/a"


def test_search_normalizes_and_dedupes_without_full_content():
    fake = FakeTavily(
        {
            "results": [
                {
                    "title": "First",
                    "url": "https://Example.com/a/",
                    "content": "snippet",
                    "score": 0.91,
                },
                {
                    "title": "Duplicate",
                    "url": "https://example.com/a#frag",
                    "content": "other",
                    "score": 0.2,
                },
                {"title": "Blank", "url": "", "content": "skip", "score": 0.8},
            ]
        }
    )
    sources = TavilyRetrieval(fake).search("battery degradation EV demand", max_results=5)

    assert sources == [
        Source(
            url="https://Example.com/a/",
            canonical_url="https://example.com/a",
            title="First",
            snippet="snippet",
            score=0.91,
        )
    ]
    query, kwargs = fake.search_calls[0]
    assert query == "battery degradation EV demand"
    assert kwargs["include_raw_content"] is False
    assert kwargs["include_answer"] is False
    assert kwargs["search_depth"] == "advanced"
    assert kwargs["max_results"] == 5


def test_search_bounds_long_queries():
    fake = FakeTavily()
    TavilyRetrieval(fake).search("word " * 200)
    assert len(fake.search_calls[0][0]) == QUERY_MAX_CHARS


def test_search_rejects_empty_query_and_unknown_depth():
    client = TavilyRetrieval(FakeTavily())
    with pytest.raises(ValueError):
        client.search("   ")
    with pytest.raises(ValueError):
        client.search("ev demand", search_depth="deep")


def test_investigate_extracts_only_pages_above_the_score_threshold():
    fake = FakeTavily(
        search_payload={
            "results": [
                {"title": "High", "url": "https://example.com/high", "content": "yes", "score": 0.8},
                {"title": "Low", "url": "https://example.com/low", "content": "no", "score": 0.4},
                {"title": "Missing", "url": "https://example.com/na", "content": "no score", "score": None},
            ]
        },
        extract_payloads=[
            {
                "results": [
                    {
                        "url": "https://example.com/high",
                        "raw_content": "relevant chunk",
                    }
                ],
                "failed_results": [],
            }
        ],
    )

    sources = TavilyRetrieval(fake).investigate("battery concerns", chunks_per_source=2)

    assert [source.url for source in sources] == ["https://example.com/high"]
    assert sources[0].content == "relevant chunk"
    assert sources[0].snippet == "yes"
    urls, kwargs = fake.extract_calls[0]
    assert urls == ["https://example.com/high"]
    assert kwargs["query"] == "battery concerns"
    assert kwargs["chunks_per_source"] == 2
    assert kwargs["extract_depth"] == "basic"


def test_investigate_skips_extract_when_nothing_is_relevant():
    fake = FakeTavily(
        search_payload={
            "results": [
                {"title": "Low", "url": "https://example.com/low", "content": "no", "score": 0.2}
            ]
        }
    )
    sources = TavilyRetrieval(fake).investigate("obscure claim")
    assert len(sources) == 1
    assert sources[0].content is None
    assert fake.extract_calls == []


def test_extract_caps_urls_and_retries_failed_pages_in_advanced_mode():
    urls = [f"https://example.com/{index}" for index in range(25)]
    fake = FakeTavily(
        extract_payloads=[
            {
                "results": [{"url": "https://example.com/0", "raw_content": "ok"}],
                "failed_results": [{"url": "https://example.com/1", "error": "timeout"}],
            },
            {
                "results": [{"url": "https://example.com/1", "raw_content": "recovered"}],
                "failed_results": [],
            },
        ]
    )

    sources = TavilyRetrieval(fake).extract(urls, query="facts")

    assert len(fake.extract_calls[0][0]) == 20
    assert fake.extract_calls[1][0] == ["https://example.com/1"]
    assert fake.extract_calls[1][1]["extract_depth"] == "advanced"
    assert {source.url: source.content for source in sources} == {
        "https://example.com/0": "ok",
        "https://example.com/1": "recovered",
    }


def test_extract_without_query_does_not_request_chunks():
    fake = FakeTavily(extract_payloads=[{"results": [], "failed_results": []}])
    TavilyRetrieval(fake).extract(["https://example.com/a"])
    assert "chunks_per_source" not in fake.extract_calls[0][1]
    assert "query" not in fake.extract_calls[0][1]


def test_missing_api_key_uses_keyless_search_and_extract(monkeypatch):
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    monkeypatch.setattr("searchhax.retrieval.load_dotenv", lambda *args, **kwargs: False)
    client = build_client()
    assert client._keyless is True
    assert client.headers["X-Tavily-Access-Mode"] == "keyless"
    assert "Authorization" not in client.headers
