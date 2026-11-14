import os

import pytest

pytestmark = pytest.mark.integration


@pytest.mark.skipif(not os.environ.get("TELEM_API_KEY"), reason="TELEM_API_KEY missing")
def test_telem_live_smoke():
    from exploration.backend.retrieval import RetrievalClient

    client = RetrievalClient(dry_run=False)
    bundle = client.search("when was the International Space Station launched")
    assert bundle.session_id
    assert bundle.interaction_id
    assert bundle.provider_call_count >= 1
    assert bundle.documents
