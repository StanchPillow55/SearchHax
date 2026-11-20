"""Lantern trace, branching, and knowledge-map honesty.

These tests use fixtures and a fake retrieval client. They do not call a paid LLM.
"""

from fastapi.testclient import TestClient

from exploration.backend.main import create_app
from exploration.backend.orchestrator import Orchestrator
from exploration.backend.retrieval import FetchedPage, MergedDocument, ProviderHit, SearchBundle
from exploration.backend.trace import build_trace, create_branch, knowledge_graph, resume_branch
from shared.contracts import AttentionComponents, CreateBranchRequest, EvidenceCandidate


def _down(*_args, **_kwargs):
    raise RuntimeError("convergence down")


def _stages(trace) -> list[tuple]:
    return [
        (event.stage, event.summary, event.payload.get("query"), event.payload.get("stop_reason"))
        for event in trace.events
    ]


class FakeRetrieval:
    def __init__(self):
        self.dry_run = True
        self.queries: list[str] = []

    def search(self, query, session_id=None, guard=None):
        if guard is not None:
            guard.authorize_search()
        self.queries.append(query)
        url = "https://counter.example/energy"
        hit = ProviderHit(
            provider="fixture",
            url=url,
            canonical_url=url,
            title="Energy costs",
            snippet="Energy costs rose.",
            rank=1,
        )
        document = MergedDocument(
            canonical_url=url,
            title="Energy costs",
            snippet="Energy costs rose.",
            providers=["fixture"],
            hits=[hit],
        )
        return SearchBundle(
            query=query,
            documents=[document],
            provider_hits=[hit],
            provider_call_count=0,
            dry_run=True,
            raw={"note": "test"},
        )

    def fetch(self, urls, session_id=None, guard=None):
        if guard is not None and urls:
            guard.authorize_fetch(len(urls))
        return [
            FetchedPage(
                url=url,
                canonical_url=url,
                title="Energy costs",
                content="Energy costs rose after the announcement and may undermine the conclusion.",
                status="ok",
                provider="fixture",
                from_cache=False,
            )
            for url in urls
        ]


def _orchestrator(tmp_path, name: str) -> Orchestrator:
    orchestrator = Orchestrator(tmp_path / name)
    orchestrator.post = _down
    return orchestrator


def test_replayed_run_returns_the_same_trace(tmp_path):
    orchestrator = _orchestrator(tmp_path, "replay.sqlite")
    export = orchestrator.run_story_c()
    first = build_trace(orchestrator.database, export.investigation.id).model_dump(mode="json")
    second = build_trace(orchestrator.database, export.investigation.id).model_dump(mode="json")
    assert first == second
    assert first["question"] == export.investigation.question

    again = _orchestrator(tmp_path, "replay-b.sqlite")
    second_run = again.run_story_c()
    left = build_trace(orchestrator.database, export.investigation.id)
    right = build_trace(again.database, second_run.investigation.id)
    assert _stages(left) == _stages(right)
    assert left.question == right.question
    assert [node.type for node in left.nodes] == [node.type for node in right.nodes]


def test_zero_search_runs_do_not_draw_search_nodes(tmp_path):
    orchestrator = _orchestrator(tmp_path, "zero.sqlite")
    profile = orchestrator.run_profile()
    profile_trace = build_trace(orchestrator.database, profile.investigation.id)
    assert profile.investigation.usage.search_calls == 0
    assert profile.investigation.usage.fetch_calls == 0
    assert profile.investigation.usage.llm_calls == 0
    assert profile_trace.search_event_count == 0
    assert profile_trace.fetch_event_count == 0
    assert profile_trace.llm_event_count == 0
    assert profile_trace.artifact_notes
    assert all(node.type != "search" for node in profile_trace.nodes)
    assert all(note.activity == "fixture_corpus" for note in profile_trace.artifact_notes)
    assert all("not a web search" in note.note.lower() or "did not web-search" in note.note.lower() for note in profile_trace.artifact_notes)

    baseline = orchestrator.run_story_c(follow_up=False)
    baseline_trace = build_trace(orchestrator.database, baseline.investigation.id)
    assert baseline.investigation.usage.search_calls == 0
    assert baseline_trace.search_event_count == 0
    assert all(node.type != "search" for node in baseline_trace.nodes)
    assert any(node.type == "ingest" for node in baseline_trace.nodes)
    assert all(note.activity == "fixture_corpus" for note in baseline_trace.artifact_notes)


def test_story_c_local_scan_is_a_search_but_candidates_stay_fixture(tmp_path):
    orchestrator = _orchestrator(tmp_path, "story.sqlite")
    export = orchestrator.run_story_c()
    trace = build_trace(orchestrator.database, export.investigation.id)
    searches = [node for node in trace.nodes if node.type == "search"]
    assert len(searches) == 1
    assert searches[0].payload["kind"] == "local_corpus_scan"
    assert searches[0].payload["result_urls"] == []
    assert searches[0].epistemic_status == "unknown"
    assert all(note.activity == "fixture_corpus" for note in trace.artifact_notes)
    assert trace.question == export.investigation.question


def test_scores_do_not_verify_a_source_and_unknowns_stay_unknown(tmp_path):
    orchestrator = _orchestrator(tmp_path, "scores.sqlite")
    export = orchestrator.run_profile()
    trace = build_trace(orchestrator.database, export.investigation.id)
    assert trace.artifact_notes
    top = max(trace.artifact_notes, key=lambda note: note.knowledge_value_score or 0)
    assert (top.knowledge_value_score or 0) > 0
    assert top.verified is False
    assert top.epistemic_status == "unknown"
    for note in trace.artifact_notes:
        assert note.verified is False
        assert note.epistemic_status == "unknown"
        assert note.origin_kind == "unknown"
        if not note.bridge_trigger:
            assert note.bridge_status == "unknown"
            assert note.bridge_trigger is None
    for node in trace.nodes:
        assert node.epistemic_status != "verified"
        assert node.payload.get("verified") is not True
        assert node.payload.get("verified_success") is not True
        if node.type in {"ranking", "ingest", "retrieval", "search"}:
            assert node.epistemic_status == "unknown"
            assert node.verification_basis == "none"
    for node in trace.nodes:
        if node.type != "evidence":
            continue
        if node.epistemic_status == "supported":
            assert node.verification_basis in {"claim_status", "relationship_status"}
            assert node.payload.get("verified") is False


def test_incomplete_trace_is_not_invented_and_stays_on_its_question(tmp_path):
    orchestrator = _orchestrator(tmp_path, "incomplete.sqlite")
    first = orchestrator.create("Which source belongs to question A?")
    second = orchestrator.create("Which source belongs to question B?")
    export = orchestrator.get(first.id)
    export.candidates.append(
        EvidenceCandidate(
            id="cand_manual_a",
            url="https://historical.example/a",
            title="Historical candidate A",
            snippet="Stored without a search event.",
            attention=AttentionComponents(R=1, G=1, D=1, F=1, score=0.99),
        )
    )
    orchestrator.database.replace_graph_rows(export)
    first.usage.search_calls = 2
    orchestrator.database.update_investigation(first, None)

    trace_a = build_trace(orchestrator.database, first.id)
    trace_b = build_trace(orchestrator.database, second.id)
    assert trace_a.incomplete is True
    assert "not reconstructed" in (trace_a.incomplete_reason or "").lower() or "not drawn" in (trace_a.incomplete_reason or "").lower()
    assert trace_a.nodes == []
    assert trace_a.edges == []
    assert all(node.type != "search" for node in trace_a.nodes)
    assert trace_a.artifact_notes[0].activity == "reused_or_historical"
    assert trace_a.artifact_notes[0].verified is False
    assert trace_a.artifact_notes[0].origin_kind == "unknown"
    assert trace_a.artifact_notes[0].bridge_status == "unknown"
    assert trace_a.artifact_notes[0].attention_score == 0.99
    assert trace_a.question == "Which source belongs to question A?"
    assert trace_b.question == "Which source belongs to question B?"
    assert [note.id for note in trace_b.artifact_notes] == []
    assert "cand_manual_a" not in {note.id for note in trace_b.artifact_notes}


def test_branch_interventions_append_a_new_trace(tmp_path):
    orchestrator = _orchestrator(tmp_path, "branch.sqlite")
    fake = FakeRetrieval()
    orchestrator.retrieval = fake
    parent = orchestrator.run_story_c()
    parent_id = parent.investigation.id
    before = build_trace(orchestrator.database, parent_id).model_dump(mode="json")
    parent_claims = [claim.id for claim in parent.claims]
    checkpoint_id = parent.checkpoints[0].id

    challenge = create_branch(
        orchestrator,
        parent_id,
        CreateBranchRequest(
            from_checkpoint_id=checkpoint_id,
            objective="Investigate whether energy costs undermine the current conclusion",
            intervention_type="challenge_evidence",
            constraints={"max_searches": 1},
        ),
    )
    child_before = orchestrator.get(challenge.child_investigation_id)
    assert child_before.investigation.question == "Investigate whether energy costs undermine the current conclusion"
    assert parent.investigation.question == orchestrator.get(parent_id).investigation.question
    assert [claim.id for claim in orchestrator.get(parent_id).claims] == parent_claims
    inherited = build_trace(orchestrator.database, challenge.child_investigation_id)
    assert inherited.search_event_count == 0
    assert all(node.type != "search" for node in inherited.nodes)
    assert inherited.artifact_notes
    assert all(note.activity == "reused_or_historical" for note in inherited.artifact_notes)
    assert build_trace(orchestrator.database, parent_id).model_dump(mode="json") == before

    resume_branch(orchestrator, challenge.id)
    after_parent = build_trace(orchestrator.database, parent_id).model_dump(mode="json")
    assert after_parent == before
    assert orchestrator.database.search_queries(parent_id) == [row for row in orchestrator.database.search_queries(parent_id)]
    child = build_trace(orchestrator.database, challenge.child_investigation_id)
    assert child.question == "Investigate whether energy costs undermine the current conclusion"
    assert child.parent_investigation_id == parent_id
    assert fake.queries == ["Investigate whether energy costs undermine the current conclusion"]
    searches = [node for node in child.nodes if node.type == "search"]
    assert len(searches) == 1
    assert searches[0].payload["query"] == fake.queries[0]
    assert searches[0].epistemic_status == "unknown"
    current = [note for note in child.artifact_notes if note.activity == "current_run"]
    inherited_notes = [note for note in child.artifact_notes if note.activity == "reused_or_historical"]
    assert current
    assert inherited_notes
    assert all(note.verified is False for note in current)
    parent_event_ids = {event["id"] for event in before["events"]}
    assert parent_event_ids.isdisjoint({event.id for event in child.events})
    convergence = [node for node in child.nodes if node.type == "convergence"]
    assert convergence
    assert convergence[-1].payload["verified_success"] is False

    continued = create_branch(
        orchestrator,
        parent_id,
        CreateBranchRequest(
            from_checkpoint_id=parent.checkpoints[-1].id,
            objective="Keep going from the saved checkpoint",
            intervention_type="continue",
            constraints={"max_searches": 1},
        ),
    )
    parent_after_continue_create = build_trace(orchestrator.database, parent_id).model_dump(mode="json")
    assert parent_after_continue_create == before
    resume_branch(orchestrator, continued.id)
    assert build_trace(orchestrator.database, parent_id).model_dump(mode="json") == before
    continued_trace = build_trace(orchestrator.database, continued.child_investigation_id)
    assert continued_trace.question == parent.investigation.question
    assert continued_trace.intervention_type == "continue"
    assert any(node.type == "search" for node in continued_trace.nodes)
    assert continued.child_investigation_id != challenge.child_investigation_id


def test_knowledge_map_does_not_treat_retrieval_or_scores_as_knowing(tmp_path):
    orchestrator = _orchestrator(tmp_path, "knowledge.sqlite")
    export = orchestrator.run_profile()
    graph = knowledge_graph(orchestrator.database, investigation_id=export.investigation.id)
    assert graph.question == export.investigation.question
    assert graph.profile_id == "profile_ai_infrastructure"
    known = [node for node in graph.nodes if node.epistemic_state == "known"]
    assert known
    assert all(node.basis == "profile_prior" and node.confirmed is False for node in known)
    encountered = [node for node in graph.nodes if node.epistemic_state == "encountered"]
    assert len(encountered) == len(export.documents)
    assert all(node.confirmed is False for node in encountered)
    frontier = [node for node in graph.nodes if node.epistemic_state == "frontier"]
    assert frontier
    assert all(node.inferred is True and node.confirmed is False for node in frontier)
    titles = {node.label for node in encountered}
    top = max(export.candidates, key=lambda item: item.knowledge_value.score if item.knowledge_value else 0)
    assert top.title in titles
    assert all(node.epistemic_state != "known" or node.basis == "profile_prior" for node in graph.nodes)
    assert any("not learning" in note.lower() or "not sourced" in note.lower() or "ranking signal" in note.lower() for note in graph.notes)

    app = create_app(tmp_path / "api.sqlite")
    app.state.orchestrator.post = _down
    client = TestClient(app)
    created = client.post("/api/exploration/fixtures/profile")
    assert created.status_code == 200
    investigation_id = created.json()["investigation"]["id"]
    trace = client.get(f"/api/exploration/investigations/{investigation_id}/trace")
    assert trace.status_code == 200
    body = trace.json()
    assert body["question"] == created.json()["investigation"]["question"]
    assert all(node["type"] != "search" for node in body["nodes"])
    missing = client.post(
        f"/api/exploration/investigations/{investigation_id}/branches",
        json={"from_checkpoint_id": "missing", "objective": "nope", "intervention_type": "fork"},
    )
    assert missing.status_code == 404
    confirmed = client.post(
        "/api/exploration/profile/knowledge-assertions",
        json={
            "profile_id": "profile_ai_infrastructure",
            "investigation_id": investigation_id,
            "subject": "NVIDIA",
            "predicate": "invested_in",
            "object": "CoreWeave",
            "text": "NVIDIA invested in CoreWeave.",
            "epistemic_state": "known",
            "basis": "user_confirmation",
        },
    )
    assert confirmed.status_code == 200
    confirmed_nodes = [
        node for node in confirmed.json()["nodes"]
        if node["basis"] == "profile_prior" and "CoreWeave" in node["label"]
    ]
    assert confirmed_nodes
    assert confirmed_nodes[0]["confirmed"] is True
    assert all(node["epistemic_state"] != "known" for node in confirmed.json()["nodes"] if node["epistemic_state"] == "encountered")
