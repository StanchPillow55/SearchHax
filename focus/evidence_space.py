"""Evidence context space beside the Lantern Map.

Both views read the investigation the backend already stored. This module does
not rank candidates and does not open its own branch store. Forks go through
the Lantern branch callback.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from context_space import (
    AXIS_X,
    AXIS_Y,
    AXIS_Z,
    compare_points,
    component_spec,
    evidence_id_for_node,
    latest_eligible_checkpoint,
    node_id_for_evidence,
    point_by_id,
    points_from_recorded,
    preview_ranking,
)

_COMPONENT_DIR = Path(__file__).resolve().parent / "context_space_component"
_PLOTLY_JS = _COMPONENT_DIR / "plotly.min.js"
_COMPONENT = components.declare_component("evidence_context_space", path=str(_COMPONENT_DIR))


def render_evidence_space(api, trace, checkpoints, investigation, on_branch, selected_node=None, *, chart_only: bool = False) -> None:
    investigation_id = investigation["id"]
    st.markdown("**Evidence context space**")
    st.caption(
        "The Lantern Map is how this investigation progressed. This space is where the same recorded evidence sits. "
        "Selection is shared. A dot is not a checkpoint, and a score is not verification."
    )
    checkpoint_id = _checkpoint_choice(investigation_id, checkpoints)
    view = points_from_recorded(trace, checkpoints, checkpoint_id, investigation)
    _banners(view)
    if not view.points:
        st.info(view.reason or "No evidence points.")
        return
    _sync_from_node(investigation_id, selected_node, view.points)
    selected = _selected_id(investigation_id, view.points)
    spec = component_spec(
        view.points,
        selected_id=selected,
        camera=st.session_state.get(_camera_key(investigation_id, view.checkpoint_id)),
        title="Evidence context space",
        color_by="action",
    )
    if chart_only:
        picked = _draw_chart(spec, f"context-space-{investigation_id}-{view.checkpoint_id}")
        _apply_chart_pick(investigation_id, view.checkpoint_id, picked, view.points, trace.get("nodes") or [])
        chosen = _evidence_selector(investigation_id, view.points)
        point = point_by_id(view.points, chosen)
        if point is not None:
            _remember_selection(investigation_id, point.evidence_id, trace.get("nodes") or [], view.points)
        st.caption(
            "Axes are the policy scores recorded on the checkpoint: intent alignment, novelty, and unresolved-question alignment. "
            "The list selects the same evidence as the map. A score is not verification."
        )
        if view.omitted:
            st.caption(f"{view.omitted} recorded candidate(s) have no policy coordinates in this snapshot and are not plotted.")
        _preview(api, investigation_id, view, on_branch)
        return
    chart_column, inspector_column = st.columns([3, 2])
    with chart_column:
        picked = _draw_chart(spec, f"context-space-{investigation_id}-{view.checkpoint_id}")
        _apply_chart_pick(investigation_id, view.checkpoint_id, picked, view.points, trace.get("nodes") or [])
        st.caption(
            "Axes are the policy scores recorded on the checkpoint: intent alignment, novelty, and unresolved-question alignment. "
            "Retrieval attention and knowledge value are not these axes. Drag to rotate. The list selects the same evidence if a click does not."
        )
        if view.omitted:
            st.caption(f"{view.omitted} recorded candidate(s) have no policy coordinates in this snapshot and are not plotted.")
    with inspector_column:
        chosen = _evidence_selector(investigation_id, view.points)
        point = point_by_id(view.points, chosen)
        if point is not None:
            _remember_selection(investigation_id, point.evidence_id, trace.get("nodes") or [], view.points)
            _inspector(api, investigation_id, point, checkpoints, on_branch)
    _preview(api, investigation_id, view, on_branch)


def render_evidence_compare(api, family, current_id, current_trace, current_checkpoints, get_json, on_open) -> None:
    left_id = st.session_state.get("lantern_compare_left")
    right_id = st.session_state.get("lantern_compare_right")
    if not left_id or not right_id:
        return
    st.markdown("**Evidence space comparison**")
    st.caption(
        "Same axes and the same 0–1 scales. Shared evidence is on both lanterns. "
        "New evidence was recorded on only one. Conflicting means the recorded relationship signatures disagree. "
        "A different score is not by itself a conflict, and neither side is rewritten."
    )
    try:
        left = _view_for(get_json, api, left_id, current_id, current_trace, current_checkpoints)
        right = _view_for(get_json, api, right_id, current_id, current_trace, current_checkpoints)
    except Exception as exc:
        st.error(f"Could not compare the recorded spaces: {exc}")
        return
    if not left.view.points and not right.view.points:
        st.info("Neither lantern has recorded evidence coordinates. Nothing was invented for the comparison.")
        return
    compared = compare_points(left.view.points, right.view.points, left.snapshot, right.snapshot)
    counts = {
        role: len({(point.url or point.evidence_id) for point in compared if point.compare_role == role})
        for role in ("shared", "new", "conflict")
    }
    summary = st.columns(3)
    summary[0].metric("Shared points", counts["shared"])
    summary[1].metric("New points", counts["new"])
    summary[2].metric("Conflicting points", counts["conflict"])
    spec = component_spec(
        compared,
        selected_id=None,
        camera=st.session_state.get("context-compare-camera"),
        title="Lantern comparison",
        color_by="role",
    )
    picked = _draw_chart(spec, f"context-compare-{left_id}-{right_id}-{counts['shared']}-{counts['new']}-{counts['conflict']}")
    if isinstance(picked, dict) and picked.get("camera"):
        st.session_state["context-compare-camera"] = picked["camera"]
    labels = {point.evidence_id + point.branch_id: _compare_label(point) for point in compared}
    if not labels:
        return
    choice = st.selectbox("Compared evidence", list(labels), format_func=lambda item: labels[item], key="context-compare-choice")
    point = next(item for item in compared if item.evidence_id + item.branch_id == choice)
    st.write(f"{point.compare_role} · {point.title or point.evidence_id}")
    st.caption(f"Investigation {point.investigation_id} · lantern {point.branch_id}")
    st.write(
        f"Intent alignment {point.intent_alignment:.3f} · novelty {point.novelty:.3f} · "
        f"unresolved-question alignment {point.unresolved_alignment:.3f}"
    )
    if point.investigation_id != current_id:
        st.button(
            "Open the lantern that recorded this",
            key=f"open-compare-{point.investigation_id}",
            on_click=_open_lantern,
            args=(on_open, api, point.investigation_id),
        )


def _view_for(get_json, api, investigation_id, current_id, current_trace, current_checkpoints):
    if investigation_id == current_id:
        trace, checkpoints = current_trace, current_checkpoints
    else:
        trace = get_json(api, f"/api/exploration/investigations/{investigation_id}/trace")
        checkpoints = get_json(api, f"/api/exploration/investigations/{investigation_id}/checkpoints")
    view = points_from_recorded(trace, checkpoints, None)
    snapshot = {}
    if view.checkpoint_id:
        chosen = next((item for item in checkpoints if item.get("id") == view.checkpoint_id), None)
        snapshot = ((chosen or {}).get("state_json") or {}).get("snapshot") or {}
    return _Loaded(view, snapshot)


class _Loaded:
    def __init__(self, view, snapshot):
        self.view = view
        self.snapshot = snapshot


def _checkpoint_choice(investigation_id: str, checkpoints: list[dict]) -> str | None:
    options = ["latest", *[item["id"] for item in checkpoints]]
    labels = {"latest": "Latest recorded checkpoint"}
    for item in checkpoints:
        labels[item["id"]] = f"Step {item.get('step')} · {item.get('summary') or item['id']}"
    widget = f"context-checkpoint-{investigation_id}"
    applied_key = f"checkpoint-applied-{investigation_id}"
    view = st.session_state.get("lantern_checkpoint_view")
    if view not in options:
        view = None
    if st.session_state.get(applied_key, "missing") != view:
        st.session_state[widget] = view or "latest"
        st.session_state[applied_key] = view
    choice = st.selectbox("Checkpoint snapshot", options, format_func=lambda item: labels.get(item, item), key=widget)
    selected = None if choice == "latest" else choice
    if selected != view:
        st.session_state["lantern_checkpoint_view"] = selected
        st.session_state[applied_key] = selected
    return selected


def _banners(view) -> None:
    if view.playback:
        st.info(f"Checkpoint playback for {view.checkpoint_id}. Showing the saved snapshot. Coordinates were not regenerated.")
    else:
        st.caption("Showing the latest saved checkpoint. The chart reads that snapshot and does not rescore it.")
    if view.incomplete and view.incomplete_reason:
        st.warning(view.incomplete_reason)
    if view.status == "blocked":
        st.warning(view.reason or "This investigation is blocked. Missing results were not invented.")
    elif view.status == "stopped":
        st.caption(f"Stopped ({view.stop_reason or 'no stop reason recorded'}).")
    if view.stop_reason == "unresolved_uncertainty":
        st.warning("Unresolved stop. This is not verified convergence and not a verified answer.")
    if view.search_event_count == 0 and view.points:
        st.caption("No searches were recorded. These points are recorded evidence, not search events.")
    if view.decision_source:
        st.caption(f"Decision source on this snapshot: {view.decision_source}. A fallback is not a controller verdict.")


def _sync_from_node(investigation_id: str, node: dict | None, points) -> None:
    if not node:
        return
    mapped = evidence_id_for_node(node, points)
    node_key = f"evidence-synced-node-{investigation_id}"
    if not mapped or node.get("id") == st.session_state.get(node_key):
        return
    widget = f"evidence-point-{investigation_id}"
    st.session_state[widget] = mapped
    st.session_state[f"evidence-synced-evidence-{investigation_id}"] = mapped
    st.session_state[node_key] = node.get("id")
    st.session_state[f"chart-applied-{investigation_id}"] = mapped


def _selected_id(investigation_id: str, points) -> str | None:
    widget = f"evidence-point-{investigation_id}"
    current = st.session_state.get(widget)
    ids = [point.evidence_id for point in points]
    if current in ids:
        return current
    return ids[0]


def _evidence_selector(investigation_id: str, points) -> str:
    widget = f"evidence-point-{investigation_id}"
    ids = [point.evidence_id for point in points]
    labels = {point.evidence_id: f"{point.action} · {point.title or point.evidence_id}" for point in points}
    if st.session_state.get(widget) not in ids:
        st.session_state[widget] = ids[0]
    return st.selectbox("Evidence in this space", ids, format_func=lambda item: labels[item], key=widget)


def _remember_selection(investigation_id: str, evidence_id: str, nodes: list, points) -> None:
    synced = f"evidence-synced-evidence-{investigation_id}"
    if evidence_id == st.session_state.get(synced):
        return
    st.session_state[synced] = evidence_id
    st.session_state[f"chart-applied-{investigation_id}"] = evidence_id
    target = node_id_for_evidence(evidence_id, nodes, points)
    node_widget = f"lantern-node-{investigation_id}"
    if target and target != st.session_state.get(node_widget):
        st.session_state["lantern_force_node"] = target
        st.session_state[f"evidence-synced-node-{investigation_id}"] = target
        st.rerun()


def _apply_chart_pick(investigation_id: str, checkpoint_id: str | None, picked, points, nodes: list) -> None:
    if not isinstance(picked, dict):
        return
    if picked.get("camera"):
        st.session_state[_camera_key(investigation_id, checkpoint_id)] = picked["camera"]
    evidence_id = picked.get("evidence_id")
    ids = {point.evidence_id for point in points}
    applied = f"chart-applied-{investigation_id}"
    if evidence_id not in ids or evidence_id == st.session_state.get(applied):
        return
    st.session_state[f"evidence-point-{investigation_id}"] = evidence_id
    st.session_state[f"evidence-synced-evidence-{investigation_id}"] = evidence_id
    st.session_state[applied] = evidence_id
    target = node_id_for_evidence(evidence_id, nodes, points)
    if target:
        st.session_state["lantern_force_node"] = target
        st.session_state[f"evidence-synced-node-{investigation_id}"] = target
    st.rerun()


def _inspector(api, investigation_id, point, checkpoints, on_branch) -> None:
    st.markdown(f"**{point.title or point.evidence_id}**")
    st.caption(f"Evidence {point.evidence_id} · investigation {point.investigation_id} · lantern {point.branch_id}")
    if point.activity == "fixture_corpus":
        st.caption("Fixture corpus. This was not a web search, and encountering it is not knowing it.")
    elif point.activity == "reused_or_historical":
        st.caption("Inherited or already stored. Encountered is not known, and this run did not search it again.")
    elif point.activity == "unknown":
        st.caption("How this evidence entered the investigation was not recorded. It is unknown, not filled in.")
    st.write(f"Source: {point.url or 'No URL recorded.'}")
    origin = point.provenance or {}
    st.write(
        f"Origin: {origin.get('origin_kind') or 'unknown'} · "
        f"origin id: {origin.get('origin_id') or 'unknown'} · "
        f"provider: {origin.get('provider') or 'unknown'}"
    )
    if point.url:
        st.link_button("Inspect source", point.url)
    else:
        st.caption("Inspect source is unavailable because no URL was recorded.")
    st.write(f"Passage: {point.passage or 'No passage recorded.'}")
    st.markdown("**Policy scores recorded on the checkpoint**")
    st.write(f"{AXIS_X}: {point.intent_alignment:.3f}")
    st.write(f"{AXIS_Y}: {point.novelty:.3f}")
    st.write(f"{AXIS_Z}: {point.unresolved_alignment:.3f}")
    st.write(f"Policy action: {point.action}. {point.reason}")
    st.caption("These scores choose what to inspect next. They are not factual confidence.")
    if point.attention_score is None:
        st.caption("No retrieval-attention score was recorded.")
    else:
        st.caption(
            f"Retrieval attention {point.attention_score:.3f} "
            f"(relevance {point.attention_relevance if point.attention_relevance is not None else 'not recorded'}, "
            f"gap {point.attention_gap if point.attention_gap is not None else 'not recorded'}). "
            "Attention is not the policy position and not verification."
        )
    if point.knowledge_value_score is None:
        st.caption("No knowledge-value score was recorded. Nothing here is marked as user knowledge.")
    else:
        st.caption(
            f"Knowledge value {point.knowledge_value_score:.3f} was recorded. "
            "It is not factual confidence and it does not mean the user knows the passage."
        )
        if point.knowledge_value_novelty is not None:
            st.caption(
                f"Knowledge-value novelty N={point.knowledge_value_novelty:.3f} is a separate component. "
                "It is not the policy novelty axis."
            )
        if point.bridge_trigger:
            st.caption(f"Recorded bridge trigger: {point.bridge_trigger}. A missing trigger stays unknown.")
    st.write(f"Linked relationship status: {point.epistemic_status} ({point.verification_basis}).")
    if point.epistemic_status == "unknown":
        st.caption("Unknown is not verified. The policy action does not change that.")
    if point.relationships:
        st.dataframe(pd.DataFrame(point.relationships), use_container_width=True, hide_index=True)
    else:
        st.caption("No relationships were recorded for this evidence in the snapshot.")
    convergence = point.convergence or {}
    st.markdown("**Convergence decision on this snapshot**")
    st.write(f"Source: {convergence.get('decision_source') or 'unknown'}")
    st.write(f"Stop reason: {convergence.get('stop_reason') or 'none recorded'}")
    st.write(convergence.get("rationale") or "No rationale recorded.")
    if convergence.get("unresolved"):
        st.warning("Unresolved stop. Not verified convergence.")
    eligible = latest_eligible_checkpoint(checkpoints, point.evidence_id, point.document_id, point.url)
    if eligible is None:
        st.caption("No saved checkpoint contains this evidence. A lantern was not offered, because a dot is not a place to resume.")
        return
    st.caption(
        f"Branch from checkpoint {eligible['id']} (step {eligible.get('step')}), "
        "the latest saved checkpoint that contains this evidence. The original investigation stays as it was."
    )
    st.text_input("Branch objective", key=f"evidence-objective-{investigation_id}", placeholder="Why this lantern branches")
    searches = st.number_input("Max searches on the child", min_value=1, max_value=2, value=1, key=f"evidence-searches-{investigation_id}")
    actions = st.columns(2)
    actions[0].button(
        "Challenge evidence",
        key=f"evidence-challenge-{investigation_id}",
        on_click=_fork_evidence,
        args=(on_branch, api, investigation_id, checkpoints, "challenge_evidence", int(searches)),
    )
    actions[1].button(
        "Fork Lantern",
        key=f"evidence-fork-{investigation_id}",
        on_click=_fork_evidence,
        args=(on_branch, api, investigation_id, checkpoints, "fork", int(searches)),
    )


def _preview(api, investigation_id, view, on_branch) -> None:
    st.markdown("**Preview search priorities**")
    st.caption(
        "Weights reorder the recorded coordinates for a preview. Dot positions and stored scores stay as they were. "
        "Recording the priorities creates a new lantern from this checkpoint. It does not rewrite the parent."
    )
    columns = st.columns(4)
    columns[0].slider("Intent alignment weight", 0.0, 1.0, 1.0, key=f"preview-intent-{investigation_id}")
    columns[1].slider("Novelty weight", 0.0, 1.0, 1.0, key=f"preview-novelty-{investigation_id}")
    columns[2].slider("Unresolved-question weight", 0.0, 1.0, 1.0, key=f"preview-unresolved-{investigation_id}")
    knowledge_recorded = any(point.knowledge_value_score is not None for point in view.points)
    columns[3].slider(
        "Knowledge-value weight",
        0.0,
        1.0,
        0.0,
        key=f"preview-knowledge-{investigation_id}",
        disabled=not knowledge_recorded,
        help="Enabled only when a knowledge-value score was recorded. It is not user mastery.",
    )
    if not knowledge_recorded:
        st.caption("Knowledge-value weight is off because no knowledge-value score was recorded.")
    weights = {
        "intent": st.session_state[f"preview-intent-{investigation_id}"],
        "novelty": st.session_state[f"preview-novelty-{investigation_id}"],
        "unresolved": st.session_state[f"preview-unresolved-{investigation_id}"],
        "knowledge_value": st.session_state[f"preview-knowledge-{investigation_id}"] if knowledge_recorded else None,
    }
    ranked = preview_ranking(view.points, weights)
    labels = {point.evidence_id: point.title or point.evidence_id for point in view.points}
    st.dataframe(
        pd.DataFrame([{"preview rank": index + 1, "evidence": labels[evidence_id], "preview score": round(score, 3)} for index, (evidence_id, score) in enumerate(ranked)]),
        use_container_width=True,
        hide_index=True,
    )
    st.caption("Preview score is not stored and is not factual confidence.")
    if not view.checkpoint_id:
        st.caption("There is no checkpoint to branch from, so the priorities cannot be recorded.")
        return
    st.button(
        "Record these priorities as a new lantern",
        key=f"preview-apply-{investigation_id}",
        on_click=_apply_priorities,
        args=(on_branch, api, investigation_id, view.checkpoint_id, knowledge_recorded),
    )


def _draw_chart(spec: dict, key: str):
    if not spec.get("traces"):
        return None
    if not _PLOTLY_JS.exists():
        st.warning("The 3D click chart could not load Plotly.js. The evidence list still selects the recorded point.")
        _fallback_chart(spec)
        return None
    return _COMPONENT(spec=spec, key=key, default=None)


def _fallback_chart(spec: dict) -> None:
    import plotly.graph_objects as go

    figure = go.Figure()
    for trace in spec["traces"]:
        figure.add_trace(
            go.Scatter3d(
                x=trace["x"],
                y=trace["y"],
                z=trace["z"],
                mode="markers",
                name=trace["name"],
                text=trace["text"],
                marker={"size": 6, "color": trace["color"]},
            )
        )
    figure.update_layout(
        title=spec.get("title") or "Evidence context space",
        scene={
            "xaxis": {"title": AXIS_X, "range": [0, 1]},
            "yaxis": {"title": AXIS_Y, "range": [0, 1]},
            "zaxis": {"title": AXIS_Z, "range": [0, 1]},
        },
        margin={"l": 0, "r": 0, "t": 40, "b": 0},
    )
    st.plotly_chart(figure, use_container_width=True)


def _open_lantern(on_open, api, investigation_id) -> None:
    on_open(api, investigation_id, keep_family=True)


def _fork_evidence(on_branch, api, investigation_id, checkpoints, intervention, max_searches) -> None:
    max_searches = int(st.session_state.get(f"evidence-searches-{investigation_id}") or max_searches)
    evidence_id = st.session_state.get(f"evidence-point-{investigation_id}")
    checkpoint = latest_eligible_checkpoint(checkpoints, evidence_id) if evidence_id else None
    if checkpoint is None:
        st.session_state["lantern_notice"] = (
            "No saved checkpoint contains that evidence. A lantern was not created. A plotted point is not a resume position."
        )
        return
    title = evidence_id
    for row in (checkpoint.get("state_json") or {}).get("policy_space") or []:
        if row.get("evidence_id") == evidence_id:
            title = row.get("title") or evidence_id
            break
    typed = (st.session_state.get(f"evidence-objective-{investigation_id}") or "").strip()
    if intervention == "challenge_evidence":
        objective = typed or f"Challenge the recorded evidence: {title}"
    else:
        objective = typed or f"Fork from the recorded evidence: {title}"
    on_branch(
        api,
        investigation_id,
        checkpoint["id"],
        intervention,
        objective,
        max_searches,
        {"max_searches": max_searches},
    )


def _apply_priorities(on_branch, api, investigation_id, checkpoint_id, knowledge_recorded) -> None:
    intent = float(st.session_state.get(f"preview-intent-{investigation_id}") or 0)
    novelty = float(st.session_state.get(f"preview-novelty-{investigation_id}") or 0)
    unresolved = float(st.session_state.get(f"preview-unresolved-{investigation_id}") or 0)
    knowledge = float(st.session_state.get(f"preview-knowledge-{investigation_id}") or 0) if knowledge_recorded else None
    objective = (
        "Recorded search priorities. "
        f"intent={intent:.2f}, novelty={novelty:.2f}, unresolved={unresolved:.2f}, "
        f"knowledge_value={'not recorded' if knowledge is None else f'{knowledge:.2f}'}. "
        "Stored scores were not rewritten."
    )
    constraints = {
        "intent_weight": intent,
        "novelty_weight": novelty,
        "unresolved_weight": unresolved,
        "knowledge_value_weight": knowledge,
    }
    on_branch(api, investigation_id, checkpoint_id, "fork", objective, 1, constraints)


def _compare_label(point) -> str:
    return f"{point.compare_role} · {point.title or point.evidence_id} · {point.branch_id}"


def _camera_key(investigation_id: str, checkpoint_id: str | None) -> str:
    return f"context-camera-{investigation_id}-{checkpoint_id or 'latest'}"
