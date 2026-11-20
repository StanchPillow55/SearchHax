"""A disclosed-fact hit does not hide a later sentence on the same page."""

from __future__ import annotations

from exploration.backend.extraction import extract_document

PAGE = (
    "NVIDIA has invested $2 billion in CoreWeave. "
    "NVIDIA later said that investment was cancelled and the stake is zero."
)
CANCELLED = "NVIDIA later said that investment was cancelled and the stake is zero."


def test_later_sentence_is_not_hidden_by_the_investment_regex():
    calls = {"count": 0}

    class Client:
        configured = True

        def complete_json(self, system, user):
            del system, user
            calls["count"] += 1
            return (
                {
                    "relationships": [
                        {
                            "subject": "NVIDIA",
                            "predicate": "investment_status",
                            "object": "cancelled",
                            "quote": CANCELLED,
                            "kind": "factual",
                        }
                    ],
                    "gaps": [],
                },
                {"total_tokens": 1},
            )

    batch = extract_document(
        PAGE,
        url="https://news.example/a",
        document_id="doc-1",
        version_id="ver-1",
        version_hash="hash-1",
        question="Did NVIDIA cancel the CoreWeave investment?",
        llm=Client(),
    )
    stored = [(rel.predicate, rel.object_name, rel.status) for rel in batch.relationships]
    assert calls["count"] == 1, (calls["count"], stored)
    assert any(rel.object_name == "cancelled" for rel in batch.relationships), stored
