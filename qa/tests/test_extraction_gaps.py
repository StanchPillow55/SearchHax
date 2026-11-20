"""Model notes about the excerpt are not investigation questions."""

from __future__ import annotations


from exploration.backend.extraction import relationships_from_llm_payload
from exploration.backend.planner import generate_actions

NOTE = (
    "The excerpt is truncated mid-sentence at the funding statement "
    "('supported by Cont'), so the funding source and study details are unavailable."
)
PAGE = "This document is a research report submitted to the U.S. Department of Justice. Funding continues in the full document."


def test_truncated_excerpt_note_is_not_a_follow_up_query():
    # NOTE was first observed in the live demo recorded on 2026-11-14 (an open question in
    # story_a). The 2026-11-20 re-recording, made with this fix, no longer stores it, so the
    # defect is reproduced from the recorded text itself rather than from the demo file.
    from exploration.backend.orchestrator import STORY_A_QUESTION

    batch = relationships_from_llm_payload(
        {"relationships": [], "gaps": [{"text": NOTE, "importance": 0.5}]},
        PAGE,
        document_id="doc-ojp",
        version_id="ver-ojp",
        version_hash="hash-ojp",
        question=STORY_A_QUESTION,
    )
    assert batch.relationships == []
    stored = [(question.kind, question.missing_evidence, question.text) for question in batch.questions]
    actions = generate_actions(batch.questions, [])
    queries = [action.query for action in actions]
    assert NOTE not in {item[2] for item in stored} and NOTE not in queries, (stored, queries)
