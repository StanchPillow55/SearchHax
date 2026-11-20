"""Model notes about the excerpt are not investigation questions."""

from __future__ import annotations

import json
from pathlib import Path

from exploration.backend.extraction import relationships_from_llm_payload
from exploration.backend.planner import generate_actions

NOTE = (
    "The excerpt is truncated mid-sentence at the funding statement "
    "('supported by Cont'), so the funding source and study details are unavailable."
)
PAGE = "This document is a research report submitted to the U.S. Department of Justice. Funding continues in the full document."


def test_truncated_excerpt_note_is_not_a_follow_up_query():
    recorded = json.loads(
        (Path(__file__).resolve().parents[2] / "demo" / "integrated_profile_evaluation.json").read_text()
    )
    assert NOTE in recorded["story_a"]["open_questions"]
    batch = relationships_from_llm_payload(
        {"relationships": [], "gaps": [{"text": NOTE, "importance": 0.5}]},
        PAGE,
        document_id="doc-ojp",
        version_id="ver-ojp",
        version_hash="hash-ojp",
        question=recorded["story_a"]["question"],
    )
    assert batch.relationships == []
    stored = [(question.kind, question.missing_evidence, question.text) for question in batch.questions]
    actions = generate_actions(batch.questions, [])
    queries = [action.query for action in actions]
    assert NOTE not in {item[2] for item in stored} and NOTE not in queries, (stored, queries)
