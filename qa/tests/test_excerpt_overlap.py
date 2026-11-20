"""A sentence that does not repeat the question is still sent to the model."""

from __future__ import annotations

from exploration.backend.extraction import extract_document

PAGE = (
    "NVIDIA discussed CoreWeave capacity plans for next year.\n\n"
    "The stake was cancelled."
)


def test_nonoverlapping_sentence_is_sent_to_the_model():
    seen: list[str] = []

    class Client:
        configured = True

        def complete_json(self, system, user):
            del system
            seen.append(user)
            return ({"relationships": [], "gaps": []}, {"total_tokens": 1})

    extract_document(
        PAGE,
        url="https://news.example/a",
        document_id="doc-1",
        version_id="ver-1",
        version_hash="hash-1",
        question="What did NVIDIA announce about CoreWeave capacity?",
        llm=Client(),
    )
    assert seen and "The stake was cancelled." in seen[0], seen
