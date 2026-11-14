"""One live Telem search. Skipped when TELEM_API_KEY is missing."""

from __future__ import annotations

import pytest

from exploration.backend.config import telem_configured
from exploration.backend.retrieval import RetrievalClient


@pytest.mark.integration
def test_telem_search_returns_real_results(tmp_path):
    if not telem_configured():
        pytest.skip("TELEM_API_KEY missing")
    client = RetrievalClient(
        cache_dir=tmp_path / "cache",
        dry_run=False,
        providers=("brave",),
        num_results=1,
        tier="default",
    )
    bundle = client.search("NVIDIA CoreWeave investment January 2026")
    assert bundle.dry_run is False
    assert bundle.from_cache is False
    assert bundle.session_id
    assert bundle.interaction_id
    assert bundle.documents
    assert all(document.canonical_url.startswith("http") for document in bundle.documents)
    assert any("coreweave" in (document.title or "").lower() or "nvidia" in (document.title or "").lower() for document in bundle.documents)
