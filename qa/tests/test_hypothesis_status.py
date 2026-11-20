"""A hypothesis is not stored as a supported relationship."""

from __future__ import annotations

from exploration.backend.extraction import relationships_from_llm_payload

PAGE = "NVIDIA may expand capacity next year."


def test_hypothesis_quote_is_not_a_supported_relationship():
    batch = relationships_from_llm_payload(
        {
            "relationships": [
                {
                    "subject": "NVIDIA",
                    "predicate": "may expand",
                    "object": "capacity",
                    "quote": "NVIDIA may expand capacity",
                    "kind": "hypothesis",
                }
            ]
        },
        PAGE,
        document_id="doc-hyp",
        version_id="ver-hyp",
        version_hash="hash-hyp",
        question="How do NVIDIA's investments and AI capacity expansion reinforce one another?",
    )
    supported = [(rel.kind, rel.status, rel.predicate, rel.object_name) for rel in batch.relationships if rel.status == "supported"]
    assert supported == [], supported
