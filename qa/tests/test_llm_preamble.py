"""A preamble example is not the extraction payload."""

from __future__ import annotations

import json

from exploration.backend.extraction import relationships_from_llm_payload
from exploration.backend.llm import extract_json_object

PAGE = "NVIDIA has invested $2 billion in CoreWeave."
MODEL = (
    'Example only: {"relationships": [{"subject": "NVIDIA", "predicate": "invested_in", '
    '"object": "CoreWeave", "quote": "NVIDIA has invested $2 billion in CoreWeave."}]}. '
    '{"relationships": [], "gaps": []}'
)


def test_preamble_example_is_not_stored_as_supported():
    payload = json.loads(extract_json_object(MODEL))
    batch = relationships_from_llm_payload(
        payload,
        PAGE,
        document_id="doc-1",
        version_id="ver-1",
        version_hash="hash-1",
    )
    supported = [(rel.predicate, rel.object_name, rel.status) for rel in batch.relationships if rel.status == "supported"]
    assert supported == [], (payload, supported)
