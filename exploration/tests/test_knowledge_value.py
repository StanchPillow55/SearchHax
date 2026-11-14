"""Offline knowledge-value checks. No provider calls."""

from __future__ import annotations

import json
import shutil
import socket
from pathlib import Path

import httpx
import pytest

from exploration.backend.attention import (
    DOMAIN_BRIDGES,
    WEIGHT_D,
    WEIGHT_F,
    WEIGHT_G,
    WEIGHT_R,
    domain_bridge,
    score_passage,
)
from exploration.backend.config import profile_fixture_dir
from exploration.backend.knowledge_value import contradiction_component, score_knowledge_value
from exploration.backend.orchestrator import Orchestrator
from exploration.backend.profile_run import SAMPLE_NOTE, evaluation_from_export, load_profile_fixture
from exploration.backend.retrieval import RetrievalClient
from shared.contracts import ExplorationExport, KnowledgeValue

ROOT = Path(__file__).resolve().parents[2]
CERAMIC_QUOTE = "Using a ceramic substrate leads to less package warpage for advanced packaging of advanced chips."


def _offline_retrieval(tmp_path):
    def explode(*_args, **_kwargs):
        raise AssertionError("retrieval was called")

    return RetrievalClient(
        cache_dir=tmp_path / "cache",
        dry_run=False,
        search_fn=explode,
        fetch_fn=explode,
        sleeper=lambda _seconds: None,
    )


def _down(*_args, **_kwargs):
    raise httpx.ConnectError("connection refused")


def _ceramic_text() -> str:
    return (profile_fixture_dir() / "ceramic_packaging.md").read_text(encoding="utf-8")


def _profile():
    profile, question, documents = load_profile_fixture()
    return profile, question, documents


def test_query_attention_weights_stay_in_place():
    assert (WEIGHT_R, WEIGHT_G, WEIGHT_D, WEIGHT_F) == (0.4, 0.3, 0.2, 0.1)
    scored = score_passage("GPU inference", "GPU inference benchmark", None, "2026-10-01")
    assert scored.score == pytest.approx(min(1.0, 0.4 * scored.R + 0.3 * scored.G + 0.2 * scored.D + 0.1 * scored.F))


def test_components_match_the_formula_and_are_stable():
    profile, _question, documents = _profile()
    ceramic = next(item for item in documents if item.fixture_id == "doc_ceramic_packaging").content
    first = score_knowledge_value(ceramic, profile)
    second = score_knowledge_value(ceramic, profile)
    assert first.model_dump() == second.model_dump()
    for value in (first.R, first.N, first.B, first.I, first.C, first.score):
        assert 0.0 <= value <= 1.0
    expected = 0.25 * first.R + 0.25 * first.N + 0.20 * first.B + 0.20 * first.I + 0.10 * first.C
    assert first.score == pytest.approx(min(1.0, expected))
    assert "probability" in KnowledgeValue.model_fields["score"].description or "heuristic" in KnowledgeValue.model_fields["score"].description


def test_semiconductor_bridge_is_the_live_domain_entry():
    profile, _question, _documents = _profile()
    ceramic = _ceramic_text()
    assert DOMAIN_BRIDGES["semiconductor"] == ("substrate", "ceramic", "packaging", "warpage")
    assert domain_bridge("semiconductor", ceramic) == 1.0
    assert domain_bridge("unrelated topic", ceramic) == 0.0
    scored = score_knowledge_value(ceramic, profile)
    assert scored.B == 1.0
    assert scored.bridge_trigger == "semiconductor"
    assert set(scored.bridge_terms) >= {"ceramic", "substrate", "warpage"}
    synthetic = {"camera": ("ceramic", "substrate")}
    assert score_knowledge_value(ceramic, profile, bridges=synthetic).B == 0.0
    saved = dict(DOMAIN_BRIDGES)
    try:
        DOMAIN_BRIDGES.clear()
        DOMAIN_BRIDGES.update({key: value for key, value in saved.items() if key != "semiconductor"})
        assert score_knowledge_value(ceramic, profile).B == 0.0
    finally:
        DOMAIN_BRIDGES.clear()
        DOMAIN_BRIDGES.update(saved)


def test_removing_advanced_packaging_changes_ceramic_priority():
    profile, _question, _documents = _profile()
    ceramic = _ceramic_text()
    before = score_knowledge_value(ceramic, profile)
    after = score_knowledge_value(
        ceramic,
        profile.model_copy(
            update={
                "interests": [item for item in profile.interests if item != "advanced packaging"],
                "unresolved_interests": [],
            }
        ),
    )
    assert before.score != after.score
    assert after.I == 0.0
    assert before.I > after.I


def test_contradiction_requires_the_same_predicate_and_a_different_object():
    profile, _question, documents = _profile()
    assert contradiction_component("NVIDIA invested in Lambda Labs.", profile) == 1.0
    assert contradiction_component("NVIDIA invested in CoreWeave.", profile) == 0.0
    assert contradiction_component("Capacity expansion is finished.", profile) == 1.0
    assert contradiction_component("Capacity expansion is under investigation.", profile) == 0.0
    for item in documents:
        assert score_knowledge_value(item.content, profile).C == 0.0


def test_unrelated_novelty_alone_is_not_a_discovery(tmp_path):
    profile, question, documents = _profile()
    phone = next(item for item in documents if item.fixture_id == "doc_smartphone_launch")
    scored = score_knowledge_value(phone.content, profile)
    assert scored.N == 1.0
    assert scored.B == 0.0
    assert scored.I == 0.0
    solo = score_knowledge_value("zephyr quilts orbit marigold kettles", profile)
    assert solo.B == 0.0
    assert solo.N == 1.0
    root = tmp_path / "only-novel"
    root.mkdir()
    raw = json.loads((profile_fixture_dir() / "ai_infrastructure.json").read_text(encoding="utf-8"))
    raw["documents"] = [
        {
            "id": "doc_novel_only",
            "file": "novel.md",
            "url": "https://profile-fixture.example/novel-only",
            "title": "Unrelated novelty",
            "publish_date": "2026-10-01",
        }
    ]
    (root / "ai_infrastructure.json").write_text(json.dumps(raw), encoding="utf-8")
    (root / "novel.md").write_text("zephyr quilts orbit marigold kettles\n", encoding="utf-8")
    export = Orchestrator(tmp_path / "novel.sqlite", retrieval=_offline_retrieval(tmp_path)).run_profile(root)
    assert export.investigation.metadata["discovery"]["surfaced"] is False
    assert export.investigation.question == question
    assert not any(rel.status == "supported" for rel in export.relationships)


def test_profile_run_ranks_both_ways_and_grounds_only_the_bridge(tmp_path, monkeypatch):
    def refuse(*_args, **_kwargs):
        raise AssertionError("network was called")

    monkeypatch.setattr(socket, "create_connection", refuse)
    monkeypatch.setattr(httpx.Client, "request", refuse)
    orchestrator = Orchestrator(tmp_path / "profile.sqlite", retrieval=_offline_retrieval(tmp_path))
    export = orchestrator.run_profile()
    meta = export.investigation.metadata
    assert export.investigation.question == "Which LLM benchmark results show the fastest GPU inference for AI systems?"
    assert export.investigation.decision_source is None
    assert export.investigation.usage.network_calls == 0
    assert export.investigation.usage.llm_calls == 0
    assert export.investigation.usage.provider_calls == 0
    assert export.investigation.usage.search_calls == 0
    assert meta["extraction_origin"] == "deterministic_fixture"
    assert [row["fixture_id"] for row in meta["rankings"]["B0"]] == [
        "doc_llm_benchmark",
        "doc_ceramic_packaging",
        "doc_smartphone_launch",
    ]
    assert [row["fixture_id"] for row in meta["rankings"]["B3"]] == [
        "doc_ceramic_packaging",
        "doc_llm_benchmark",
        "doc_smartphone_launch",
    ]
    assert meta["same_passage"] is False
    assert meta["comparison_note"] == (
        "B0 ordinary query ranking and B3 knowledge-value ranking select different passages on this fixed corpus."
    )
    discovery = meta["discovery"]
    assert discovery["surfaced"] is True
    assert discovery["prior_interest"] == "advanced packaging"
    assert discovery["quotation"] == CERAMIC_QUOTE
    assert discovery["bridge_trigger"] == "semiconductor"
    assert "advanced packaging" in discovery["reason"]
    assert CERAMIC_QUOTE in discovery["reason"]
    supported = [rel for rel in export.relationships if rel.status == "supported"]
    assert len(supported) == 1
    assert supported[0].subject_name == "ceramic substrate"
    assert supported[0].object_name == "less package warpage"
    versions = {item.document_id: item for item in export.document_versions}
    ceramic_doc = next(item for item in export.documents if item.origin_id == "doc_ceramic_packaging")
    span = export.evidence_spans[0]
    stored = versions[ceramic_doc.id]
    assert stored.content[span.start : span.end] == span.text == CERAMIC_QUOTE
    assert span.quote_valid is True
    assert all(rel.object_name != "CoreWeave" for rel in export.relationships)
    assert {item["origin"] for item in meta["attestations"]} == {"profile_prior"}
    assert {item["object"] for item in meta["attestations"]} == {"CoreWeave", "under investigation"}
    assert meta["unique_facts"][0]["origin"] == "sourced_fixture"
    assert meta["unique_facts"][0]["object"] == "less package warpage"
    assert "Tavily" in meta["sample_note"]
    assert "not proof" in meta["sample_note"]
    assert export.profile is not None
    assert export.profile.id == "profile_ai_infrastructure"
    assert "ceramic" not in " ".join(export.profile.interests).lower()
    orchestrator._persist(export)
    reloaded = orchestrator.reload_profile(export.investigation.id)
    assert reloaded.investigation.question == export.investigation.question
    assert reloaded.investigation.metadata["profile_snapshot"] == meta["profile_snapshot"]
    assert reloaded.investigation.metadata["rankings"] == meta["rankings"]
    assert reloaded.profile is not None
    assert reloaded.profile.model_dump() == export.profile.model_dump()
    assert orchestrator.database.search_queries(export.investigation.id) == []
    assert len(reloaded.documents) == 3
    again = orchestrator.reload_profile(export.investigation.id)
    assert again.investigation.metadata["rankings"] == reloaded.investigation.metadata["rankings"]
    export.investigation.question = "a different question"
    with pytest.raises(ValueError):
        orchestrator.database.update_investigation(export.investigation, None)


def _rank_signature(export):
    signature = {}
    for name, rows in export.investigation.metadata["rankings"].items():
        signature[name] = [
            {
                "fixture_id": row["fixture_id"],
                "attention": row["attention"],
                "knowledge_value": row["knowledge_value"],
            }
            for row in rows
        ]
    return signature


def test_rank_order_is_stable_across_runs(tmp_path):
    first = Orchestrator(tmp_path / "a.sqlite", retrieval=_offline_retrieval(tmp_path)).run_profile()
    second = Orchestrator(tmp_path / "b.sqlite", retrieval=_offline_retrieval(tmp_path)).run_profile()
    assert _rank_signature(first) == _rank_signature(second)
    assert [row["fixture_id"] for row in first.investigation.metadata["rankings"]["B0"]] == [
        row["fixture_id"] for row in second.investigation.metadata["rankings"]["B0"]
    ]
    assert [row["fixture_id"] for row in first.investigation.metadata["rankings"]["B3"]] == [
        row["fixture_id"] for row in second.investigation.metadata["rankings"]["B3"]
    ]
    assert first.investigation.metadata["discovery"]["reason"] == second.investigation.metadata["discovery"]["reason"]


def test_removing_the_bridge_trigger_does_not_surface_a_bridge(tmp_path):
    reduced = {key: value for key, value in DOMAIN_BRIDGES.items() if key != "semiconductor"}
    export = Orchestrator(tmp_path / "bridge.sqlite", retrieval=_offline_retrieval(tmp_path)).run_profile(bridges=reduced)
    ceramic = next(row for row in export.investigation.metadata["rankings"]["B3"] if row["fixture_id"] == "doc_ceramic_packaging")
    assert ceramic["knowledge_value"]["B"] == 0.0
    assert export.investigation.metadata["discovery"]["surfaced"] is False
    assert export.investigation.metadata["discovery"]["status"] == "not_a_bridge"
    assert not any(rel.status == "supported" for rel in export.relationships)


def test_invalid_quotation_rejects_the_discovery(tmp_path):
    root = tmp_path / "fixtures"
    shutil.copytree(profile_fixture_dir(), root)
    raw = json.loads((root / "ai_infrastructure.json").read_text(encoding="utf-8"))
    for item in raw["documents"]:
        if item["id"] == "doc_ceramic_packaging":
            item["candidate"]["quote"] = "this sentence is not in the document"
    (root / "ai_infrastructure.json").write_text(json.dumps(raw), encoding="utf-8")
    export = Orchestrator(tmp_path / "bad.sqlite", retrieval=_offline_retrieval(tmp_path)).run_profile(root)
    discovery = export.investigation.metadata["discovery"]
    assert discovery["surfaced"] is False
    assert discovery["rejected"] is True
    assert discovery["prior_interest"] == "advanced packaging"
    assert "this sentence is not in the document" in discovery["reason"]
    ceramic = next(row for row in export.investigation.metadata["rankings"]["B3"] if row["fixture_id"] == "doc_ceramic_packaging")
    assert ceramic["knowledge_value"]["score"] > 0.5
    assert not any(rel.status == "supported" for rel in export.relationships)
    assert export.investigation.usage.rejected_ungrounded_citations >= 1


def test_committed_profile_evaluation_matches_a_fresh_offline_run(tmp_path):
    export = Orchestrator(tmp_path / "demo.sqlite", retrieval=_offline_retrieval(tmp_path)).run_profile()
    fresh = evaluation_from_export(export)
    committed = json.loads((ROOT / "demo" / "profile_evaluation.json").read_text(encoding="utf-8"))
    assert committed["b0_order"] == fresh["b0_order"]
    assert committed["b3_order"] == fresh["b3_order"]
    assert committed["same_passage"] is False
    assert committed["network_calls"] == 0
    assert committed["llm_calls"] == 0
    assert committed["provider_calls"] == 0
    assert committed["search_calls"] == 0
    assert committed["extraction_origin"] == "deterministic_fixture"
    assert committed["surfaced_bridge"]["quotation"] == CERAMIC_QUOTE
    assert committed["surfaced_bridge"]["prior_interest"] == "advanced packaging"
    assert committed["unique_facts"] != committed["attestations"]
    assert committed["unique_facts"][0]["origin"] == "sourced_fixture"
    assert {item["origin"] for item in committed["attestations"]} == {"profile_prior"}
    assert "Tavily" in committed["sample_note"]
    assert "general LLM" in committed["sample_note"]
    assert committed["sample_note"] == SAMPLE_NOTE
    parsed = ExplorationExport.model_validate(
        {
            "investigation": export.investigation.model_dump(mode="json"),
            "profile": export.profile.model_dump(mode="json"),
            "extra_ignored": True,
        }
    )
    assert parsed.profile is not None
    assert parsed.profile.id == "profile_ai_infrastructure"


def test_story_c_shared_origin_and_contradiction_still_pass(tmp_path):
    export = Orchestrator(tmp_path / "story.sqlite", retrieval=_offline_retrieval(tmp_path), post=_down).run_story_c()
    assert export.investigation.usage.network_calls == 0
    assert export.investigation.usage.llm_calls == 0
    assert export.origin_clusters[0].origin_id == "LF-PR-2026-031"
    assert len(export.origin_clusters[0].document_ids) == 4
    assert any(
        item.conflicting_object == "$480 million" and item.supported_object == "$400 million"
        for item in export.contradictions
    )
    assert any(rel.object_name == "$480 million" and rel.status == "contradicted" for rel in export.relationships)
