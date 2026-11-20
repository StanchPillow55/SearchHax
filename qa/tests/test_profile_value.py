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


def test_live_profile_scores_candidates_and_records_the_focus_decision(tmp_path, monkeypatch):
    """A dummy key satisfies the web guard. The injected client makes no network call."""
    from shared.contracts import ResearchProfile

    from exploration.backend.focus_bridge import focus_post
    from exploration.backend.orchestrator import STORY_A_QUESTION

    monkeypatch.setenv("TELEM_API_KEY", "qa-dummy")
    text = "NVIDIA has invested $2 billion in CoreWeave. The buildout emphasizes advanced packaging."
    profile = ResearchProfile(
        id="profile-qa",
        interests=["advanced packaging"],
        goals=["packaging"],
        unresolved_interests=["advanced packaging"],
        known_claims=[],
        notes="qa",
    )

    def search_fn(query, session_id):
        del query, session_id
        search_fn.n = getattr(search_fn, "n", 0) + 1
        url = "https://news.example/a" if search_fn.n == 1 else "https://news.example/b"
        body = text if search_fn.n == 1 else "Customer demand for the capacity expansion remains unmeasured."
        return {
            "session_id": "sess-profile",
            "interaction_id": f"int-{search_fn.n}",
            "provider_runs": [
                {"provider": "brave", "results": [{"url": url, "title": "P", "summary": body, "provider": "brave"}]}
            ],
        }

    def fetch_fn(urls, session_id):
        del session_id
        body = text if urls[0].endswith("/a") else "Customer demand for the capacity expansion remains unmeasured."
        return {"results": [{"url": urls[0], "content": body, "status": "ok", "provider": "telem"}]}

    orchestrator = Orchestrator(
        tmp_path / "profile-web.sqlite",
        retrieval=RetrievalClient(
            cache_dir=tmp_path / "cache",
            dry_run=False,
            search_fn=search_fn,
            fetch_fn=fetch_fn,
            sleeper=lambda _seconds: None,
        ),
        post=focus_post,
    )
    created = orchestrator.create(STORY_A_QUESTION, mode="web", profile=profile)
    first = orchestrator.step(created.id)
    scored = [candidate.knowledge_value for candidate in first.candidates if candidate.knowledge_value is not None]
    assert scored
    assert all(0.0 <= item.score <= 1.0 for item in scored)
    assert all(candidate.attention is not None for candidate in first.candidates)
    assert {(rel.predicate, rel.status) for rel in first.relationships if rel.status == "supported"} == {
        ("invested_amount", "supported"),
        ("invested_in", "supported"),
    }
    second = orchestrator.step(created.id)
    assert second.investigation.question == STORY_A_QUESTION
    assert second.investigation.decision_source == "convergence"
    assert any(question.kind == "profile_interest" for question in second.unresolved_questions)


def test_recorded_profile_scores_match_the_formulas():
    """The committed live record's attention and knowledge-value scores match their formulas."""
    recorded = json.loads((Path(__file__).resolve().parents[2] / "demo" / "integrated_profile_evaluation.json").read_text())
    story = recorded["story_a"]
    assert story["profile_enabled"] is True
    assert story["decision_source"] == "convergence"
    assert story["decision_source_is_fallback"] is False
    for item in story["candidate_scores"]:
        attention = item["attention"]
        attention_score = 0.4 * attention["R"] + 0.3 * attention["G"] + 0.2 * attention["D"] + 0.1 * attention["F"]
        assert attention_score == attention["score"] == item["attention_score"]
        knowledge = item["knowledge_value"]
        knowledge_score = (
            0.25 * knowledge["R"]
            + 0.25 * knowledge["N"]
            + 0.20 * knowledge["B"]
            + 0.20 * knowledge["I"]
            + 0.10 * knowledge["C"]
        )
        assert knowledge_score == knowledge["score"]
        assert 0.0 <= knowledge["score"] <= 1.0


def test_recorded_profile_run_counts_every_stored_page():
    """Each stored candidate is a fetched URL or a counted cache hit."""
    recorded = json.loads((Path(__file__).resolve().parents[2] / "demo" / "integrated_profile_evaluation.json").read_text())
    story = recorded["story_a"]
    usage = story["usage"]
    stored = len(story["candidate_scores"])
    assert usage["urls_fetched"] + usage["cache_hits"] == stored, (
        usage["urls_fetched"],
        usage["cache_hits"],
        stored,
    )


def test_profile_survives_reopen(tmp_path, monkeypatch):
    """A new process sees the same profile and the scored candidate."""
    from shared.contracts import ResearchProfile

    from exploration.backend.focus_bridge import focus_post
    from exploration.backend.orchestrator import STORY_A_QUESTION

    monkeypatch.setenv("TELEM_API_KEY", "qa-dummy")
    text = "NVIDIA has invested $2 billion in CoreWeave. The buildout emphasizes advanced packaging."

    def search_fn(query, session_id):
        del query, session_id
        return {
            "session_id": "sess-reopen",
            "interaction_id": "int-reopen",
            "provider_runs": [
                {
                    "provider": "brave",
                    "results": [
                        {"url": "https://news.example/a", "title": "NVIDIA", "summary": text, "provider": "brave"}
                    ],
                }
            ],
        }

    def fetch_fn(urls, session_id):
        del session_id
        return {"results": [{"url": urls[0], "content": text, "status": "ok", "provider": "telem"}]}

    client = RetrievalClient(
        cache_dir=tmp_path / "cache",
        dry_run=False,
        search_fn=search_fn,
        fetch_fn=fetch_fn,
        sleeper=lambda _seconds: None,
    )
    path = tmp_path / "reopen.sqlite"
    created = Orchestrator(path, retrieval=client, post=focus_post).create(
        STORY_A_QUESTION,
        mode="web",
        profile=ResearchProfile(
            id="profile-qa",
            interests=["advanced packaging"],
            unresolved_interests=["advanced packaging"],
        ),
    )
    Orchestrator(path, retrieval=client, post=focus_post).step(created.id)
    reopened = Orchestrator(path, retrieval=client, post=focus_post).get(created.id)
    assert reopened.profile is not None
    assert reopened.profile.id == "profile-qa"
    assert reopened.profile.unresolved_interests == ["advanced packaging"]
    assert reopened.investigation.question == STORY_A_QUESTION
    assert [candidate.knowledge_value.score for candidate in reopened.candidates] == [0.7]

