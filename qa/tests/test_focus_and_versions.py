"""Adversarial checks for the focus handoff, versions, and the Telem call shape.

No live provider call is made.
"""

from __future__ import annotations

from datetime import datetime, timezone

from exploration.backend.convergence import build_request
from exploration.backend.database import Database
from exploration.backend.focus_bridge import evaluate_with_focus
from exploration.backend.ids import content_hash
from exploration.backend.orchestrator import STORY_A_QUESTION, Orchestrator
from exploration.backend.retrieval import RetrievalClient, _sdk_search
from shared.contracts import DocumentVersion, Investigation, InvestigationBudget


def _down(*_args, **_kwargs):
    raise RuntimeError("convergence down")


def _offline(tmp_path):
    def explode(*_args, **_kwargs):
        raise AssertionError("network was called")

    return RetrievalClient(
        cache_dir=tmp_path / "cache",
        dry_run=False,
        search_fn=explode,
        fetch_fn=explode,
        sleeper=lambda _seconds: None,
    )


def test_focus_approves_the_story_c_independence_search(tmp_path):
    """An unresolved importance-0.9 gap must still be searchable.

    Archiving the four derivative pages is not the same decision as refusing
    the follow-up that looks for a source outside that set.
    """
    orchestrator = Orchestrator(tmp_path / "story.sqlite", retrieval=_offline(tmp_path), post=_down)
    export = orchestrator.run_story_c()
    request = build_request(
        investigation_id=export.investigation.id,
        question=export.investigation.question,
        questions=export.unresolved_questions,
        candidates=export.candidates,
        actions=export.actions,
        budget=export.investigation.budget,
        usage=export.investigation.usage,
    )
    assert request.proposed_actions
    assert request.proposed_actions[0].utility >= request.budget.min_utility
    body = evaluate_with_focus(request)
    assert body["stop"] is False
    assert body["approved_action"] is not None
    assert "LF-PR-2026-031" in body["approved_action"]["query"]
    assert body["approved_action"]["id"] == request.proposed_actions[0].id


def test_distinct_document_versions_both_survive(tmp_path):
    now = datetime.now(timezone.utc)
    investigation = Investigation(
        id="inv_versions",
        question="Which text was stored?",
        budget=InvestigationBudget(),
        created_at=now,
        updated_at=now,
    )
    database = Database(tmp_path / "versions.sqlite")
    database.insert_investigation(investigation)
    first = DocumentVersion(
        id="ver_one",
        document_id="doc_same",
        content_hash=content_hash("first wording"),
        fetched_at=now,
        content="first wording",
    )
    second = DocumentVersion(
        id="ver_two",
        document_id="doc_same",
        content_hash=content_hash("second wording"),
        fetched_at=now,
        content="second wording",
    )
    assert database.insert_version_if_absent(investigation.id, first).content == "first wording"
    assert database.insert_version_if_absent(investigation.id, second).content == "second wording"
    replay = database.insert_version_if_absent(investigation.id, first)
    assert replay.content == "first wording"
    assert replay.content_hash != second.content_hash
    loaded = database.load_export(investigation.id)
    stored = {version.content: version.content_hash for version in loaded.document_versions}
    assert stored["first wording"] != stored["second wording"]
    assert len(stored) == 2


def test_checkpoint_keeps_the_controller_decision(tmp_path):
    def post(url, json, timeout):  # noqa: A002
        del url, json, timeout

        class Response:
            def raise_for_status(self):
                return None

            def json(self):
                return {
                    "stop": True,
                    "stop_reason": "low_expected_value",
                    "rationale": "controller says stop",
                    "approved_action": None,
                }

        return Response()

    orchestrator = Orchestrator(tmp_path / "checkpoint.sqlite", retrieval=_offline(tmp_path), post=post)
    export = orchestrator.run_story_c()
    assert export.investigation.decision_source == "convergence"
    assert export.decision is not None
    latest = export.checkpoints[-1]
    assert latest.state_json["decision"]["decision_source"] == "convergence"
    assert latest.state_json["decision"]["rationale"] == "controller says stop"
    assert latest.state_json["question"] == export.investigation.question
    reopened = Orchestrator(tmp_path / "checkpoint.sqlite", retrieval=_offline(tmp_path), post=_down)
    loaded = reopened.get(export.investigation.id)
    assert loaded.checkpoints[-1].state_json["decision"]["stop_reason"] == "low_expected_value"
    assert loaded.investigation.question == export.investigation.question


def test_story_a_search_formulation_does_not_replace_the_question(tmp_path, monkeypatch):
    monkeypatch.setenv("TELEM_API_KEY", "qa-dummy")
    seen: list[str] = []

    def search_fn(query, session_id):
        del session_id
        seen.append(query)
        return {"session_id": "sess-qa", "interaction_id": "int-qa", "provider_runs": []}

    def fetch_fn(urls, session_id):
        del urls, session_id
        return {"results": []}

    orchestrator = Orchestrator(
        tmp_path / "intent.sqlite",
        retrieval=RetrievalClient(
            cache_dir=tmp_path / "cache",
            dry_run=False,
            search_fn=search_fn,
            fetch_fn=fetch_fn,
            sleeper=lambda _seconds: None,
        ),
        post=_down,
    )
    investigation = orchestrator.create(STORY_A_QUESTION, mode="web")
    export = orchestrator.step(investigation.id)
    assert export.investigation.question == STORY_A_QUESTION
    assert seen == ["NVIDIA CoreWeave investment AI factories capacity 2026"]
    assert export.investigation.question not in seen


def test_sdk_search_follows_the_documented_request(monkeypatch):
    captured: dict = {}

    class Result:
        url = "https://Example.com/a/#section"
        provider = "brave"
        title = "NVIDIA CoreWeave"
        publish_date = "2026-01-26"
        rank = 1
        summary = "NVIDIA invested in CoreWeave."
        excerpt = ""

    class Run:
        provider = "brave"
        error = None
        status = 200
        results = [Result()]

    class Response:
        session_id = "sess-sdk"
        interaction_id = "int-sdk"
        status = "ok"
        by_provider = [Run()]

    class Client:
        def search(self, query, **kwargs):
            captured["query"] = query
            captured["kwargs"] = kwargs
            return Response()

        def close(self):
            captured["closed"] = True

    monkeypatch.setattr("exploration.backend.retrieval._telem_client", lambda _timeout: Client())
    bundle = _sdk_search(
        "NVIDIA CoreWeave investment",
        session_id="sess-1",
        providers=["brave", "tavily"],
        tier="default",
        num_results=3,
        timeout=30,
    )
    assert captured["closed"] is True
    assert captured["kwargs"]["include_full_content"] is False
    assert captured["kwargs"]["providers_include"] == ["brave", "tavily"]
    assert captured["kwargs"]["num_results"] == 3
    assert captured["kwargs"]["tier"] == "default"
    assert captured["kwargs"]["session"] == "sess-1"
    assert bundle.session_id == "sess-sdk"
    assert bundle.interaction_id == "int-sdk"
    assert bundle.documents[0].canonical_url == "https://example.com/a"
    assert bundle.documents[0].providers == ["brave"]
    assert bundle.provider_call_count == 1


def test_controller_stop_without_reason_code_still_stops(tmp_path, monkeypatch):
    """A controller stop has to end the investigation.

    ``stop: true`` with a rationale and no stop_reason is a usable decision.
    The loop must not stay ``running``.
    """
    monkeypatch.setenv("TELEM_API_KEY", "qa-dummy")
    calls = {"n": 0}

    def search_fn(query, session_id):
        del session_id
        calls["n"] += 1
        return {
            "session_id": "sess-stop",
            "interaction_id": "int-stop",
            "provider_runs": [
                {
                    "provider": "brave",
                    "results": [
                        {
                            "url": "https://example.com/nvidia",
                            "title": "NVIDIA",
                            "summary": "NVIDIA has invested $2 billion in CoreWeave.",
                            "provider": "brave",
                        }
                    ],
                }
            ],
        }

    def fetch_fn(urls, session_id):
        del session_id
        return {
            "results": [
                {
                    "url": urls[0],
                    "content": "NVIDIA has invested $2 billion in CoreWeave.",
                    "status": "ok",
                    "provider": "telem",
                }
            ]
        }

    def post(url, json, timeout):  # noqa: A002
        del url, json, timeout

        class Response:
            def raise_for_status(self):
                return None

            def json(self):
                return {"stop": True, "rationale": "controller says stop without a reason code"}

        return Response()

    orchestrator = Orchestrator(
        tmp_path / "stop.sqlite",
        retrieval=RetrievalClient(
            cache_dir=tmp_path / "cache",
            dry_run=False,
            search_fn=search_fn,
            fetch_fn=fetch_fn,
            sleeper=lambda _seconds: None,
        ),
        post=post,
    )
    investigation = orchestrator.create(STORY_A_QUESTION, mode="web")
    orchestrator.step(investigation.id)
    stopped = orchestrator.step(investigation.id)
    again = orchestrator.step(investigation.id)
    assert stopped.decision is not None
    assert stopped.decision.decision_source == "convergence"
    assert stopped.decision.stop is True
    assert stopped.investigation.status == "stopped"
    assert stopped.investigation.stop_reason is not None
    assert again.investigation.status == "stopped"
    assert calls["n"] == 1


def test_string_false_stop_does_not_drop_the_approved_search(tmp_path, monkeypatch):
    """The string false is not a stop. The approved search still runs."""
    monkeypatch.setenv("TELEM_API_KEY", "qa-dummy")
    text = "NVIDIA has invested $2 billion in CoreWeave."
    approved = "independent measurement of CoreWeave customer demand"
    queries: list[str] = []

    def search_fn(query, session_id):
        del session_id
        queries.append(query)
        return {
            "session_id": "sess-false",
            "interaction_id": f"int-{len(queries)}",
            "provider_runs": [
                {
                    "provider": "brave",
                    "results": [
                        {"url": "https://news.example/nvidia", "title": "NVIDIA", "summary": text, "provider": "brave"}
                    ],
                }
            ],
        }

    def fetch_fn(urls, session_id):
        del session_id
        return {"results": [{"url": urls[0], "content": text, "status": "ok", "provider": "telem"}]}

    def post(url, json, timeout):  # noqa: A002
        del url, json, timeout

        class Response:
            def raise_for_status(self):
                return None

            def json(self):
                return {
                    "stop": "false",
                    "rationale": "string false means continue",
                    "approved_action": {
                        "id": "act-demand",
                        "query": approved,
                        "reason": "the page does not state demand",
                        "utility": 0.9,
                    },
                }

        return Response()

    orchestrator = Orchestrator(
        tmp_path / "false.sqlite",
        retrieval=RetrievalClient(
            cache_dir=tmp_path / "cache-false",
            dry_run=False,
            search_fn=search_fn,
            fetch_fn=fetch_fn,
            sleeper=lambda _seconds: None,
        ),
        post=post,
    )
    investigation = orchestrator.create(STORY_A_QUESTION, mode="web")
    orchestrator.step(investigation.id)
    followed = orchestrator.step(investigation.id)
    assert followed.decision is not None
    ran_approved = approved in queries
    rejected = followed.investigation.decision_source == "fallback"
    assert ran_approved or rejected
    assert not (
        followed.investigation.decision_source == "convergence"
        and followed.decision.stop is True
        and followed.decision.approved_action is None
    )


def test_same_url_from_two_providers_is_one_focus_passage():
    from focus.focus_attention import FocusAttentionModel, Passage

    model = FocusAttentionModel(
        "NVIDIA CoreWeave investment capacity",
        unresolved_questions=("downstream product demand",),
    )
    brave = Passage(
        id="hit-brave",
        text="NVIDIA invested two billion dollars in CoreWeave capacity.",
        url="https://Example.com/story/?utm_source=news",
        title="NVIDIA",
        providers=("brave",),
    )
    tavily = Passage(
        id="hit-tavily",
        text="NVIDIA invested two billion dollars in CoreWeave capacity.",
        url="https://example.com/story/",
        title="NVIDIA",
        providers=("tavily",),
    )
    decisions = model.rank([brave, tavily])
    assert len(decisions) == 1
    assert decisions[0].passage.source_key == "https://example.com/story"
    assert 0.0 <= decisions[0].score.attention <= 1.0
