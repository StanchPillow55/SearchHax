"""Evidence context space identity, playback, and preview weights.

These tests use recorded checkpoints and fixtures. They do not call a paid LLM.
"""

from pathlib import Path

from exploration.backend.orchestrator import Orchestrator
from exploration.backend.retrieval import FetchedPage, MergedDocument, ProviderHit, SearchBundle
from exploration.backend.trace import build_trace, create_branch
from focus.context_space import (
    AXIS_X,
    AXIS_Y,
    AXIS_Z,
    compare_points,
    component_spec,
    evidence_id_for_node,
    evidence_id_from_plotly_selection,
    latest_eligible_checkpoint,
    node_id_for_evidence,
    point_by_id,
    points_from_recorded,
    preview_ranking,
)
from shared.contracts import CreateBranchRequest


def _down(*_args, **_kwargs):
    raise RuntimeError("convergence down")


class FakeRetrieval:
    def __init__(self):
        self.dry_run = True
        self.queries = []

    def search(self, query, session_id=None, guard=None):
        if guard is not None:
            guard.authorize_search()
        self.queries.append(query)
        url = "https://counter.example/energy"
        hit = ProviderHit(provider="fixture", url=url, canonical_url=url, title="Energy costs", snippet="Energy costs rose.", rank=1)
        document = MergedDocument(canonical_url=url, title="Energy costs", snippet="Energy costs rose.", providers=["fixture"], hits=[hit])
        return SearchBundle(query=query, documents=[document], provider_hits=[hit], provider_call_count=0, dry_run=True, raw={})

    def fetch(self, urls, session_id=None, guard=None):
        if guard is not None and urls:
            guard.authorize_fetch(len(urls))
        return [
            FetchedPage(url=url, canonical_url=url, title="Energy costs", content="Energy costs rose after the announcement.", status="ok", provider="fixture", from_cache=False)
            for url in urls
        ]


def _orchestrator(tmp_path, name):
    orchestrator = Orchestrator(tmp_path / name)
    orchestrator.post = _down
    return orchestrator


def _dump_checkpoints(export):
    return [item.model_dump(mode="json") for item in export.checkpoints]


def test_selection_identity_uses_recorded_ids(tmp_path):
    orchestrator = _orchestrator(tmp_path, "identity.sqlite")
    export = orchestrator.run_story_c()
    trace = build_trace(orchestrator.database, export.investigation.id).model_dump(mode="json")
    view = points_from_recorded(trace, _dump_checkpoints(export), None, export.investigation.model_dump(mode="json"))
    assert view.points
    point = view.points[0]
    assert point.evidence_id
    assert point.investigation_id == export.investigation.id
    assert point.branch_id == f"root:{export.investigation.id}"
    assert point_by_id(view.points, point.evidence_id) == point
    assert point_by_id(view.points, "missing") is None
    spec = component_spec(view.points, selected_id=point.evidence_id, camera=None, title="Evidence context space", color_by="action")
    assert spec["axis_x"] == AXIS_X
    assert spec["axis_y"] == AXIS_Y
    assert spec["axis_z"] == AXIS_Z
    flat = [value for trace_row in spec["traces"] for value in trace_row["x"]]
    assert point.intent_alignment in flat
    node = {
        "id": "evt:p0",
        "type": "evidence",
        "payload": {"document_id": point.document_id},
    }
    assert evidence_id_for_node(node, view.points) == point.evidence_id
    assert node_id_for_evidence(point.evidence_id, [node], view.points) == "evt:p0"
    assert evidence_id_for_node({"type": "search", "payload": {}}, view.points) is None


def test_branch_from_evidence_uses_an_eligible_checkpoint_and_keeps_the_parent(tmp_path):
    orchestrator = _orchestrator(tmp_path, "branch.sqlite")
    orchestrator.retrieval = FakeRetrieval()
    parent = orchestrator.run_story_c()
    parent_id = parent.investigation.id
    evidence = parent.candidates[0]
    before_trace = build_trace(orchestrator.database, parent_id).model_dump(mode="json")
    before_attention = [item.attention.model_dump() for item in parent.candidates]
    before_policy = [dict(row) for row in parent.checkpoints[-1].state_json["policy_space"]]
    checkpoint = latest_eligible_checkpoint(_dump_checkpoints(parent), evidence.id, evidence.document_id, evidence.url)
    assert checkpoint is not None
    assert checkpoint["id"] in {item.id for item in parent.checkpoints}
    assert latest_eligible_checkpoint(_dump_checkpoints(parent), "not-evidence") is None

    branch = create_branch(
        orchestrator,
        parent_id,
        CreateBranchRequest(
            from_checkpoint_id=checkpoint["id"],
            objective=f"Fork from the recorded evidence: {evidence.title}",
            intervention_type="fork",
            constraints={
                "max_searches": 1,
                "intent_weight": 0.2,
                "novelty_weight": 0.7,
                "unresolved_weight": 0.1,
                "knowledge_value_weight": None,
            },
        ),
    )
    reloaded = orchestrator.get(parent_id)
    assert build_trace(orchestrator.database, parent_id).model_dump(mode="json") == before_trace
    assert [item.attention.model_dump() for item in reloaded.candidates] == before_attention
    assert reloaded.checkpoints[-1].state_json["policy_space"] == before_policy
    assert branch.constraints.intent_weight == 0.2
    assert branch.constraints.novelty_weight == 0.7
    child = orchestrator.get(branch.child_investigation_id)
    child_policy = child.checkpoints[0].state_json["policy_space"]
    assert any(row["evidence_id"] == evidence.id for row in child_policy)
    assert all(row["branch_id"] == branch.id for row in child_policy)
    assert child.investigation.id != parent_id


def test_checkpoint_switch_reads_that_snapshot_only(tmp_path):
    orchestrator = _orchestrator(tmp_path, "switch.sqlite")
    export = orchestrator.run_story_c()
    trace = build_trace(orchestrator.database, export.investigation.id).model_dump(mode="json")
    checkpoints = _dump_checkpoints(export)
    assert len(checkpoints) >= 2
    first = points_from_recorded(trace, checkpoints, checkpoints[0]["id"])
    latest = points_from_recorded(trace, checkpoints, checkpoints[-1]["id"])
    assert first.playback is True
    assert first.checkpoint_id == checkpoints[0]["id"]
    assert [point.evidence_id for point in first.points] == [row["evidence_id"] for row in checkpoints[0]["state_json"]["policy_space"]]
    assert [point.intent_alignment for point in first.points] == [row["intent_alignment"] for row in checkpoints[0]["state_json"]["policy_space"]]
    assert [point.novelty for point in latest.points] == [row["novelty"] for row in checkpoints[-1]["state_json"]["policy_space"]]
    synthetic = [
        {
            "id": "cp_early",
            "step": 1,
            "state_json": {"policy_space": [_row("cand_a", 0.1, 0.2, 0.3)], "snapshot": {"candidates": [{"id": "cand_a"}]}},
        },
        {
            "id": "cp_late",
            "step": 2,
            "state_json": {"policy_space": [_row("cand_b", 0.7, 0.8, 0.9)], "snapshot": {"candidates": [{"id": "cand_b"}]}},
        },
    ]
    early = points_from_recorded({"events": [{}], "investigation_id": "inv"}, synthetic, "cp_early")
    late = points_from_recorded({"events": [{}], "investigation_id": "inv"}, synthetic, "cp_late")
    assert [point.evidence_id for point in early.points] == ["cand_a"]
    assert late.points[0].evidence_id == "cand_b"
    assert late.points[0].intent_alignment == 0.7
    missing = points_from_recorded({"events": [{}], "investigation_id": "inv"}, synthetic, "cp_other")
    assert missing.points == ()
    assert "not part of this investigation" in (missing.reason or "")


def test_preview_weights_do_not_mutate_stored_scores(tmp_path):
    orchestrator = _orchestrator(tmp_path, "preview.sqlite")
    export = orchestrator.run_profile()
    stored = [dict(row) for row in export.checkpoints[-1].state_json["policy_space"]]
    trace = build_trace(orchestrator.database, export.investigation.id).model_dump(mode="json")
    view = points_from_recorded(trace, _dump_checkpoints(export), export.checkpoints[-1].id)
    before = tuple(view.points)
    ranked = preview_ranking(view.points, {"intent": 0.0, "novelty": 1.0, "unresolved": 0.0, "knowledge_value": 3.0})
    assert view.points == before
    assert [dict(row) for row in orchestrator.get(export.investigation.id).checkpoints[-1].state_json["policy_space"]] == stored
    assert [item[0] for item in ranked]
    spec = component_spec(view.points, selected_id=None, camera=None, title="Evidence context space", color_by="action")
    plotted = {evidence_id: x for trace_row in spec["traces"] for evidence_id, x in zip(trace_row["evidence_id"], trace_row["x"], strict=True)}
    assert plotted[view.points[0].evidence_id] == view.points[0].intent_alignment
    flipped = [
        _point("low", 0.1, 0.9, 0.0),
        _point("high", 0.9, 0.1, 0.0),
    ]
    by_intent = [item[0] for item in preview_ranking(flipped, {"intent": 1, "novelty": 0, "unresolved": 0})]
    by_novelty = [item[0] for item in preview_ranking(flipped, {"intent": 0, "novelty": 1, "unresolved": 0})]
    assert by_intent[0] == "high"
    assert by_novelty[0] == "low"
    assert flipped[0].intent_alignment == 0.1


def test_zero_event_and_zero_search_do_not_fabricate_nodes(tmp_path):
    orchestrator = _orchestrator(tmp_path, "empty.sqlite")
    created = orchestrator.create("Which source belongs to an empty run?")
    empty = build_trace(orchestrator.database, created.id).model_dump(mode="json")
    view = points_from_recorded(empty, [], None)
    assert view.points == ()
    assert "no investigation events" in (view.reason or "").lower()

    profile = orchestrator.run_profile()
    profile_trace = build_trace(orchestrator.database, profile.investigation.id)
    assert profile_trace.search_event_count == 0
    assert all(node.type != "search" for node in profile_trace.nodes)
    profile_view = points_from_recorded(profile_trace.model_dump(mode="json"), _dump_checkpoints(profile), None)
    assert profile_view.points
    assert profile_view.search_event_count == 0
    assert {point.evidence_id for point in profile_view.points} <= {candidate.id for candidate in profile.candidates}

    story = orchestrator.run_story_c()
    story_view = points_from_recorded(
        build_trace(orchestrator.database, story.investigation.id).model_dump(mode="json"),
        _dump_checkpoints(story),
        None,
    )
    assert {point.investigation_id for point in story_view.points} == {story.investigation.id}
    assert {point.investigation_id for point in profile_view.points} == {profile.investigation.id}
    assert story.investigation.id != profile.investigation.id


def test_compare_marks_shared_new_and_conflicting_evidence():
    left = (
        _point("shared", 0.2, 0.2, 0.2, url="https://example.test/same"),
        _point("only-left", 0.4, 0.4, 0.4, url="https://example.test/left"),
    )
    right = (
        _point("shared-copy", 0.2, 0.2, 0.2, url="https://example.test/same", investigation_id="child"),
        _point("only-right", 0.6, 0.1, 0.1, url="https://example.test/right", investigation_id="child"),
    )
    left_snapshot = {"relationships": [{"document_id": "doc-shared", "predicate": "cost", "object_name": "high", "status": "supported"}]}
    right_snapshot = {"relationships": [{"document_id": "doc-shared-child", "predicate": "cost", "object_name": "low", "status": "supported"}]}
    shared = left[0]
    # document ids differ, so attach them through the point fields used by signatures
    left = (_replace_document(shared, "doc-shared"), left[1])
    right = (_replace_document(right[0], "doc-shared-child"), right[1])
    compared = compare_points(left, right, left_snapshot, right_snapshot)
    roles = {(point.url, point.compare_role) for point in compared}
    assert ("https://example.test/same", "conflict") in roles
    assert ("https://example.test/left", "new") in roles
    assert ("https://example.test/right", "new") in roles


def _row(evidence_id, intent, novelty, unresolved):
    return {
        "evidence_id": evidence_id,
        "investigation_id": "inv",
        "branch_id": "root:inv",
        "intent_alignment": intent,
        "novelty": novelty,
        "unresolved_alignment": unresolved,
        "title": evidence_id,
    }


def _point(evidence_id, intent, novelty, unresolved, url="", investigation_id="inv"):
    from focus.context_space import EvidencePoint

    return EvidencePoint(
        evidence_id=evidence_id,
        investigation_id=investigation_id,
        branch_id=f"root:{investigation_id}",
        document_id=None,
        url=url,
        title=evidence_id,
        passage="",
        intent_alignment=intent,
        novelty=novelty,
        unresolved_alignment=unresolved,
        action="consider",
        reason="",
        attention_score=None,
        attention_relevance=None,
        attention_gap=None,
        knowledge_value_score=None,
        knowledge_value_novelty=None,
        bridge_trigger=None,
        epistemic_status="unknown",
        verification_basis="none",
        relationships=(),
        provenance=None,
        convergence=None,
        activity="unknown",
    )


def _replace_document(point, document_id):
    return type(point)(**{**point.__dict__, "document_id": document_id})
