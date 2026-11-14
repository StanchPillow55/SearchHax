"""B0 single-pass baseline versus the Story C investigation.

Metrics are counted from the run that just finished. Token and dollar fields
stay null when no API reported them. Sample size is one investigation.
"""

from __future__ import annotations

import time
from pathlib import Path

from shared.contracts import BaselineReport, ExplorationExport

from exploration.backend.config import telem_configured
from exploration.backend.orchestrator import STORY_A_QUESTION, Orchestrator

STORY_C_NOTE = (
    "Story C retrieval is the local four-document fixture corpus. "
    "No Telem, Tavily, or LLM call is made. "
    "B0 reads that corpus once and does not classify shared origin or contradictions. "
    "B3 adds provenance, contradiction checks, and at most one local follow-up."
)


def run_baseline(
    *,
    story: str,
    configuration: str,
    db_path: Path,
    post=None,
) -> tuple[ExplorationExport | None, BaselineReport]:
    question = STORY_A_QUESTION if story == "A" else "Do three articles independently substantiate a company's claim?"
    if story == "A" and not telem_configured():
        return None, BaselineReport(
            story="A",
            configuration=configuration,  # type: ignore[arg-type]
            ran=False,
            blocker="TELEM_API_KEY missing",
            question=question,
            notes="Live Story A was not run. No relationships or usage counts were invented.",
        )
    if story == "A":
        return _run_story_a(configuration=configuration, db_path=db_path, post=post)
    started = time.perf_counter()
    orchestrator = Orchestrator(db_path, post=post)
    if configuration == "B0":
        export = orchestrator.run_story_c(reconcile=False, follow_up=False, classify=False, configuration="B0")
    else:
        export = orchestrator.run_story_c(configuration="B3")
    report = report_from_export(export, story="C", configuration=configuration)
    if report.latency_ms == 0:
        report.latency_ms = max(0, int((time.perf_counter() - started) * 1000))
    report.notes = STORY_C_NOTE
    return export, report


def _run_story_a(*, configuration: str, db_path: Path, post) -> tuple[ExplorationExport, BaselineReport]:
    orchestrator = Orchestrator(db_path, post=post)
    investigation = orchestrator.create(STORY_A_QUESTION, mode="web")
    investigation.usage.configuration = configuration
    orchestrator.database.update_investigation(investigation, None)
    export = orchestrator.step(investigation.id)
    if configuration == "B3":
        export = orchestrator.step(investigation.id)
    return export, report_from_export(export, story="A", configuration=configuration)


def report_from_export(export: ExplorationExport, *, story: str, configuration: str) -> BaselineReport:
    versions = {version.id: version for version in export.document_versions}
    correct = 0
    for span in export.evidence_spans:
        version = versions.get(span.version_id)
        if version and version.content[span.start : span.end] == span.text:
            correct += 1
    usage = export.investigation.usage
    return BaselineReport(
        story=story,  # type: ignore[arg-type]
        configuration=configuration,  # type: ignore[arg-type]
        ran=True,
        blocker=export.investigation.blocker,
        question=export.investigation.question,
        search_calls=usage.search_calls,
        provider_calls=usage.provider_calls,
        urls_fetched=usage.urls_fetched,
        llm_calls=usage.llm_calls,
        llm_tokens=usage.llm_tokens,
        supported_relationships=sum(1 for rel in export.relationships if rel.status == "supported"),
        contradicted_relationships=sum(1 for rel in export.relationships if rel.status == "contradicted"),
        insufficient_relationships=sum(1 for rel in export.relationships if rel.status == "insufficient"),
        hypothesis_relationships=sum(1 for rel in export.relationships if rel.status == "hypothesis"),
        correct_citations=correct,
        rejected_ungrounded_citations=usage.rejected_ungrounded_citations,
        contradiction_detections=len(export.contradictions),
        shared_origin_detected=any(len(cluster.document_ids) >= 2 for cluster in export.origin_clusters),
        latency_ms=usage.latency_ms,
        cost_usd=usage.cost_usd,
        network_calls=usage.network_calls,
        notes="",
    )
