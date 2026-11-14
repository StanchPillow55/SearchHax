"""Offline profile ranking. No live provider call is made."""

from __future__ import annotations

import json
from pathlib import Path

from exploration.backend.orchestrator import Orchestrator
from exploration.backend.profile_run import evaluation_from_export
from exploration.backend.retrieval import RetrievalClient

COMMITTED = Path(__file__).resolve().parents[2] / "demo" / "profile_evaluation.json"


def _explode(*_args, **_kwargs):
    raise AssertionError("profile reload called a provider")


def test_profile_run_stays_offline_and_the_quote_is_exact(tmp_path):
    """The fixed corpus ranks without a provider, and the surfaced quote is the stored sentence."""
    path = tmp_path / "profile.sqlite"
    export = Orchestrator(path).run_profile()
    usage = export.investigation.usage
    assert usage.network_calls == 0
    assert usage.provider_calls == 0
    assert usage.llm_calls == 0
    assert usage.search_calls == 0
    assert export.investigation.decision_source is None
    supported = [rel for rel in export.relationships if rel.status == "supported"]
    assert [(rel.subject_name, rel.predicate, rel.object_name) for rel in supported] == [
        ("ceramic substrate", "reduces_warpage", "less package warpage")
    ]
    priors = {("nvidia", "invested_in", "coreweave"), ("capacity expansion", "expansion_status", "under investigation")}
    assert not any(
        (rel.subject_name.casefold(), rel.predicate.casefold(), rel.object_name.casefold()) in priors
        for rel in supported
    )
    assert export.evidence_spans
    for span in export.evidence_spans:
        version = next(item for item in export.document_versions if item.id == span.version_id)
        assert version.content[span.start : span.end] == span.text
    fresh = RetrievalClient(
        cache_dir=tmp_path / "fresh",
        dry_run=False,
        search_fn=_explode,
        fetch_fn=_explode,
        sleeper=lambda _seconds: None,
    )
    reopened = Orchestrator(path, retrieval=fresh)
    loaded = reopened.reload_profile(export.investigation.id)
    stepped = reopened.step(export.investigation.id)
    assert loaded.investigation.usage.network_calls == 0
    assert stepped.investigation.status == "stopped"
    assert len(stepped.relationships) == len(export.relationships)


def test_committed_profile_evaluation_matches_a_fresh_run(tmp_path):
    """The written profile metrics match a new offline run."""
    export = Orchestrator(tmp_path / "profile.sqlite").run_profile()
    fresh = evaluation_from_export(export)
    committed = json.loads(COMMITTED.read_text())
    for key in (
        "network_calls",
        "provider_calls",
        "llm_calls",
        "search_calls",
        "b0_order",
        "b3_order",
        "b0_selected",
        "b3_selected",
        "same_passage",
        "extraction_origin",
    ):
        assert fresh[key] == committed[key]
    assert fresh["surfaced_bridge"]["quotation"] == committed["surfaced_bridge"]["quotation"]
    assert fresh["surfaced_bridge"]["surfaced"] is True
    for side in ("B0", "B3"):
        for actual, recorded in zip(fresh["rankings"][side], committed["rankings"][side], strict=True):
            assert actual["fixture_id"] == recorded["fixture_id"]
            assert actual["attention"]["score"] == recorded["attention"]["score"]
            assert actual["knowledge_value"]["score"] == recorded["knowledge_value"]["score"]
            assert actual["knowledge_value"]["C"] == recorded["knowledge_value"]["C"] == 0.0
