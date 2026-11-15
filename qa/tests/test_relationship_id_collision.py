"""Different grounded relationships do not share one id."""

from __future__ import annotations

from exploration.backend.extraction import relationships_from_llm_payload

PAGE = (
    "See NVIDIA and CoreWeave\nextra here.\n"
    "NVIDIA\ninvested_in extra note."
)


def test_newline_in_a_name_does_not_drop_the_other_relationship():
    batch = relationships_from_llm_payload(
        {
            "relationships": [
                {
                    "subject": "NVIDIA",
                    "predicate": "invested_in",
                    "object": "CoreWeave\nextra",
                    "quote": "See NVIDIA and CoreWeave\nextra here.",
                    "kind": "factual",
                },
                {
                    "subject": "NVIDIA\ninvested_in",
                    "predicate": "CoreWeave",
                    "object": "extra",
                    "quote": "NVIDIA\ninvested_in extra note.",
                    "kind": "factual",
                },
            ],
            "gaps": [],
        },
        PAGE,
        document_id="doc-1",
        version_id="ver-1",
        version_hash="hash-1",
        question="What happened?",
    )
    stored = [(rel.subject_name, rel.predicate, rel.object_name, rel.status) for rel in batch.relationships]
    assert len(stored) == 2, stored
    assert {item[2] for item in stored} == {"CoreWeave\nextra", "extra"}
