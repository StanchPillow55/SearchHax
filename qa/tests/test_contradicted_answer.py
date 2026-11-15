"""A contradicted amount is not labeled as supported evidence."""

from __future__ import annotations

from exploration.backend.answer import _citations_from_export
from exploration.backend.orchestrator import Orchestrator


def test_contradicted_amount_is_not_labeled_supported(tmp_path):
    orchestrator = Orchestrator(tmp_path / "story-c.sqlite")
    export = orchestrator.run_story_c()
    citations = [
        (citation.marker, citation.status)
        for citation in _citations_from_export(export)
        if "$480 million" in citation.quote
    ]
    assert citations and all(status == "contradicted" for _, status in citations), citations
