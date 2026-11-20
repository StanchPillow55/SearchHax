"""Lantern Workspace: investigation map over recorded events."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import requests
import streamlit as st
import streamlit.components.v1 as components

from canvas_layout import collapse_evidence
from context_space import latest_eligible_checkpoint, points_from_recorded
from evidence_space import render_evidence_compare, render_evidence_space

_COMPONENT = components.declare_component(
    "lantern_workspace",
    path=str(Path(__file__).resolve().parent / "lantern_component"),
)


def sync_lantern_family(investigation_id: str) -> None:
    family = list(st.session_state.get("lantern_family") or [])
    if investigation_id not in family:
        st.session_state["lantern_root"] = investigation_id
        st.session_state["lantern_family"] = [investigation_id]
        st.session_state["lantern_selected"] = None
        st.session_state["lantern_checkpoint_view"] = None
        st.session_state["lantern_family_choice"] = investigation_id
        st.session_state.pop("lantern_compare_left", None)
        st.session_state.pop("lantern_compare_right", None)


def render_lantern_workspace(export: dict, api: str) -> None:
    sync_lantern_family(export["investigation"]["id"])

    @st.fragment
    def _workspace() -> None:
        _render_body(api)

    _workspace()


def _render_body(api: str) -> None:
    current = st.session_state["export"]["investigation"]
    investigation_id = current["id"]
    question = current["question"]
    try:
        trace = _get(api, f"/api/exploration/investigations/{investigation_id}/trace")
        checkpoints = _get(api, f"/api/exploration/investigations/{investigation_id}/checkpoints")
        branches = _get(api, f"/api/exploration/investigations/{investigation_id}/branches")
        root = _origin(api, investigation_id, branches)
        if root != investigation_id:
            branches = _get(api, f"/api/exploration/investigations/{root}/branches")
    except requests.RequestException as exc:
        st.error(f"Lantern workspace could not read the backend: {exc}")
        return
    if trace.get("question") != question:
        st.error("The trace question does not match the investigation on screen. The map is not shown.")
        return
    st.session_state["lantern_root"] = root
    family = _family_ids(root, branches, investigation_id)
    st.session_state["lantern_family"] = family
    st.query_params["investigation"] = investigation_id
    _canvas(api, trace, checkpoints, branches, family, investigation_id, question, root)


def _canvas(api, trace, checkpoints, branches, family, investigation_id, question, root) -> None:
    state = st.session_state.get("lantern_branch_state") or {}
    if state.get("message"):
        if state.get("status") == "failed":
            st.error(state["message"])
        elif state.get("status") == "pending":
            st.info(state["message"])
        else:
            st.success(state["message"])
    if trace.get("incomplete"):
        st.warning(trace.get("incomplete_reason") or "This trace is incomplete. No events were invented.")
    view_mode = "knowledge" if st.session_state.get("lantern_view_choice") == "Knowledge" else "investigation"
    left, center, right = st.columns([1.05, 2.45, 1.35], gap="small")
    with left:
        _navigator(api, family, branches, investigation_id, question, root)
    nodes = [] if trace.get("incomplete") else list(trace.get("nodes") or [])
    expanded = set(st.session_state.get("lantern_expanded_groups") or [])
    shown, edges = collapse_evidence(nodes, list(trace.get("edges") or []), expanded)
    knowledge = _load_knowledge(api, investigation_id, question) if view_mode == "knowledge" else None
    with center:
        if view_mode == "knowledge":
            _knowledge_map(knowledge, investigation_id, question)
        elif not nodes:
            st.info("No investigation nodes are drawn. An empty or incomplete trace stays empty.")
            _map(trace, [], edges=[], kind="investigation", title=question, subtitle=_trace_subtitle(trace), selected_id=None, graph_key=f"{investigation_id}:empty")
        else:
            selected_id = st.session_state.get("lantern_force_node") or st.session_state.get(f"lantern-node-{investigation_id}")
            _map(
                trace,
                shown,
                edges=edges,
                kind="investigation",
                title=question,
                subtitle=_trace_subtitle(trace) + " Repeated claims are grouped. Expand a group to see every passage.",
                selected_id=selected_id,
                graph_key=f"{investigation_id}:{','.join(sorted(expanded))}:{len(shown)}",
            )
    with right:
        if view_mode == "knowledge":
            _knowledge_inspector(api, investigation_id, knowledge)
        else:
            _canvas_inspector(api, trace, checkpoints, investigation_id, question, nodes, shown)
    with st.expander("3D evidence space", expanded=False):
        st.caption("Same investigation and checkpoint as the map. Axes stay intent alignment, novelty, and unresolved-question alignment.")
        node = _selected_node(nodes, shown, investigation_id)
        render_evidence_space(
            api, trace, checkpoints, st.session_state["export"]["investigation"], _branch,
            selected_node=node, chart_only=True,
        )
    with st.expander("Technical details", expanded=False):
        _artifact_table(trace.get("artifact_notes") or [])
        _lantern_tab(api, trace, branches, family, investigation_id, checkpoints)


def _navigator(api, family, branches, investigation_id, question, root) -> None:
    st.markdown("**Lanterns**")
    st.caption("Parent and child investigations from the branch records. Opening one does not change the other.")
    st.radio("Canvas", ["Investigation", "Knowledge"], key="lantern_view_choice", horizontal=True)
    if investigation_id != root:
        st.button("Back to original", on_click=_open_investigation, args=(api, root), kwargs={"keep_family": True}, use_container_width=True)
    labels = {item: _investigation_label(api, item, investigation_id, question) for item in family}
    children = {branch.get("child_investigation_id"): branch for branch in branches}
    for item in family:
        branch = children.get(item)
        prefix = "Current" if item == investigation_id else ("Original" if item == root else "Child")
        detail = ""
        if branch:
            detail = f" · {branch.get('intervention_type') or 'branch'}"
        st.button(
            f"{prefix}{detail}: {labels.get(item, item)}",
            key=f"open-{item}",
            on_click=_open_investigation,
            args=(api, item),
            kwargs={"keep_family": True},
            use_container_width=True,
            disabled=item == investigation_id,
        )
    if not any(branch.get("child_investigation_id") for branch in branches):
        st.caption("No child lantern yet. Select a checkpoint and fork from the inspector.")
    st.button("Load offline profile trace", on_click=_load_profile, args=(api,), use_container_width=True)


def _canvas_inspector(api, trace, checkpoints, investigation_id, question, nodes, shown) -> None:
    st.markdown("**Inspector**")
    if not shown and not nodes:
        st.caption("Nothing is selected. An empty trace has no actions to run.")
        _status_banner(trace, st.session_state["export"]["investigation"])
        return
    selected = _select_node(shown or nodes, investigation_id)
    node = next((item for item in (shown or nodes) if item["id"] == selected), None)
    if node is None:
        st.caption("The selection is not on this investigation.")
        return
    _status_banner(trace, st.session_state["export"]["investigation"])
    _action_bar(api, node, trace, checkpoints, investigation_id, question)
    st.caption(node.get("label") or node.get("type"))
    with st.expander("Recorded details", expanded=False):
        _inspector(api, node, trace, checkpoints, investigation_id)


def _selected_node(nodes, shown, investigation_id):
    selected = st.session_state.get("lantern_force_node") or st.session_state.get(f"lantern-node-{investigation_id}")
    pool = shown or nodes
    return next((item for item in pool if item["id"] == selected), None)


def _status_banner(trace, investigation) -> None:
    status = investigation.get("status") or "unknown"
    stop = investigation.get("stop_reason") or "none recorded"
    searches = trace.get("search_event_count", 0)
    if not trace.get("events"):
        st.warning("Zero events recorded. No search or evidence nodes are drawn.")
    elif searches == 0:
        st.caption(f"Status {status}. Stop {stop}. Zero searches recorded, so no search nodes are drawn.")
    elif stop == "unresolved_uncertainty" or status == "unresolved":
        st.warning(f"Status {status}. Stop {stop}. Unresolved is not verified convergence.")
    else:
        st.caption(f"Status {status}. Stop {stop}. Recorded searches: {searches}.")


def _action_bar(api, node, trace, checkpoints, investigation_id, question) -> None:
    kind = node.get("type")
    st.caption("Fork records a child and keeps the parent. Challenge and continue search on that child and can be billable.")
    if kind == "evidence_group":
        key = (node.get("payload") or {}).get("group_key")
        st.button("Expand passages", key=f"expand-{key}", on_click=_expand_group, args=(key,))
        return
    if kind == "evidence":
        _evidence_actions(api, node, checkpoints, investigation_id)
        return
    if kind == "checkpoint":
        _checkpoint_actions(api, node, investigation_id)
        return
    if kind == "convergence":
        _convergence_actions(api, node, checkpoints, investigation_id)
        return
    st.caption("Select a checkpoint, evidence group, or convergence node to branch.")


def _evidence_actions(api, node, checkpoints, investigation_id) -> None:
    payload = node.get("payload") or {}
    eligible = latest_eligible_checkpoint(
        checkpoints, payload.get("claim_id") or node["id"], payload.get("document_id"), None,
    )
    if eligible is None:
        st.caption("No saved checkpoint contains this evidence. A dot or passage is not itself a resume point.")
        return
    st.caption(f"Branch from checkpoint {eligible['id']}, the latest one that contains this evidence.")
    st.text_input("Branch objective", key=f"objective-{eligible['id']}", placeholder="What the child lantern should investigate")
    _branch_buttons(api, investigation_id, eligible["id"], include_continue=False)


def _convergence_actions(api, node, checkpoints, investigation_id) -> None:
    if not checkpoints:
        st.caption("This decision has no saved checkpoint, so a child lantern cannot be started from it.")
        return
    payload = node.get("payload") or {}
    questions = payload.get("unresolved_questions") or []
    checkpoint_id = checkpoints[-1]["id"]
    if questions:
        st.selectbox("Unresolved alternative", questions, key=f"objective-{checkpoint_id}")
    else:
        st.text_input("Branch objective", key=f"objective-{checkpoint_id}", placeholder="Alternative to pursue")
    st.caption(f"Uses checkpoint {checkpoint_id}. The convergence node stays on the parent.")
    _branch_buttons(api, investigation_id, checkpoint_id, include_continue=True)


def _checkpoint_actions(api, node, investigation_id) -> None:
    checkpoint_id = (node.get("payload") or {}).get("checkpoint_id")
    if not checkpoint_id:
        st.caption("This checkpoint has no id, so it cannot be branched.")
        return
    st.button("Return to this checkpoint", key=f"view-{checkpoint_id}", on_click=_view_checkpoint, args=(checkpoint_id,))
    st.text_input("Branch objective", key=f"objective-{checkpoint_id}", placeholder="What the child lantern should investigate")
    _branch_buttons(api, investigation_id, checkpoint_id, include_continue=True)


def _branch_buttons(api, investigation_id, checkpoint_id, *, include_continue: bool) -> None:
    st.number_input("Max searches on the child", min_value=1, max_value=2, value=1, key=f"searches-{checkpoint_id}")
    st.button("Fork Lantern", key=f"fork-{checkpoint_id}", on_click=_branch, args=(api, investigation_id, checkpoint_id, "fork", "", 1), use_container_width=True)
    st.button("Challenge evidence", key=f"challenge-{checkpoint_id}", on_click=_branch, args=(api, investigation_id, checkpoint_id, "challenge_evidence", "", 1), use_container_width=True, help="Billable when live retrieval is configured.")
    if include_continue:
        st.button("Continue investigation", key=f"continue-{checkpoint_id}", on_click=_branch, args=(api, investigation_id, checkpoint_id, "continue", "", 1), use_container_width=True, help="Billable when live retrieval is configured.")


def _expand_group(key: str) -> None:
    expanded = set(st.session_state.get("lantern_expanded_groups") or [])
    if key:
        expanded.add(key)
    st.session_state["lantern_expanded_groups"] = sorted(expanded)


def _load_knowledge(api, investigation_id, question):
    try:
        graph = _get(api, f"/api/exploration/profile/knowledge-graph?investigation_id={investigation_id}")
    except requests.RequestException as exc:
        return {"error": f"Knowledge map could not be loaded: {exc}"}
    if graph.get("question") and graph["question"] != question:
        return {"error": "The knowledge map is for a different question than the one on screen, so it is not shown."}
    return graph


def _knowledge_map(graph, investigation_id, question) -> None:
    if graph.get("error"):
        st.error(graph["error"])
        return
    nodes = graph.get("nodes") or []
    if not nodes:
        st.info("No profile is stored on this investigation, and there are no confirmed assertions. Nothing is inferred.")
        return
    labels = _knowledge_labels()
    spec_nodes = _knowledge_spec(nodes, labels)
    stored_edges = _stored_knowledge_edges(graph)
    _map(
        {"incomplete": False, "incomplete_reason": None},
        spec_nodes,
        edges=stored_edges,
        kind="knowledge",
        title=question,
        subtitle="Edges appear only when a relationship was stored. Encountered is not known. Knowledge value is not mastery.",
        selected_id=st.session_state.get(f"lantern-node-knowledge-{investigation_id}"),
        graph_key=f"knowledge:{investigation_id}:{len(spec_nodes)}:{len(stored_edges)}",
        layout="categories",
    )


def _lantern_tab(api, trace, branches, family, investigation_id, checkpoints) -> None:
    st.markdown("**Branches** inherit a checkpoint. New events land on the child. The parent history stays as it was.")
    if not branches:
        st.caption("No branches yet. Fork, challenge, or continue from a checkpoint on the Investigation tab.")
    else:
        st.dataframe(pd.DataFrame([
            {
                "branch": item["id"],
                "child": item["child_investigation_id"],
                "from checkpoint": item["from_checkpoint_id"],
                "intervention": item["intervention_type"],
                "objective": item.get("objective") or "",
            }
            for item in branches
        ]), use_container_width=True, hide_index=True)
    st.markdown("**Compare two recorded traces**")
    if len(family) < 2:
        st.caption("A comparison appears after a second investigation is in this family.")
        return
    left_col, right_col = st.columns(2)
    with left_col:
        left = st.selectbox("Left trace", family, key="lantern_compare_left")
    with right_col:
        right = st.selectbox("Right trace", family, index=min(1, len(family) - 1), key="lantern_compare_right")
    try:
        left_trace = trace if left == investigation_id else _get(api, f"/api/exploration/investigations/{left}/trace")
        right_trace = trace if right == investigation_id else _get(api, f"/api/exploration/investigations/{right}/trace")
    except requests.RequestException as exc:
        st.error(f"Could not load a comparison trace: {exc}")
        return
    columns = st.columns(2)
    for column, item, title in ((columns[0], left_trace, "Left"), (columns[1], right_trace, "Right")):
        with column:
            st.markdown(f"**{title} question:** {item.get('question')}")
            st.caption(
                f"Searches recorded: {item.get('search_event_count', 0)}. "
                f"Fetches recorded: {item.get('fetch_event_count', 0)}. Incomplete: {item.get('incomplete')}."
            )
            for event in item.get("events") or []:
                st.write(f"{event['sequence']}. {event['stage']} — {event['summary']}")
    render_evidence_compare(api, family, investigation_id, trace, checkpoints, _get, _open_investigation)


def _knowledge_labels() -> dict:
    return {
        "interested": "Interest",
        "known": "Previously known",
        "encountered": "Encountered",
        "uncertain": "Uncertain",
        "frontier": "Frontier",
    }


def _knowledge_spec(nodes, labels) -> list:
    return [
        {
            "id": node["id"],
            "type": node["epistemic_state"],
            "label": node["label"],
            "kicker": f"{labels.get(node['epistemic_state'], node['epistemic_state'])} · {node.get('basis') or 'recorded'}",
            "epistemic_status": "unresolved" if node["epistemic_state"] == "frontier" else "unknown",
        }
        for node in nodes
    ]


def _stored_knowledge_edges(graph) -> list:
    return [
        {"id": edge["id"], "source": edge["source"], "target": edge["target"], "kind": "sequence"}
        for edge in graph.get("edges") or []
        if edge.get("source") != edge.get("target") and edge.get("basis")
    ]


def _knowledge_inspector(api, investigation_id, graph) -> None:
    st.markdown("**Inspector**")
    if graph.get("error"):
        st.error(graph["error"])
        return
    for note in graph.get("notes") or []:
        st.caption(note)
    nodes = graph.get("nodes") or []
    if not nodes:
        st.caption("Nothing is inferred. Encountered material is not treated as known, and no frontier was invented.")
    else:
        _knowledge_selection(api, investigation_id, graph, nodes)
    with st.expander("Correct or confirm an assertion", expanded=False):
        _assertion_form(api, investigation_id, graph.get("profile_id"))


def _knowledge_selection(api, investigation_id, graph, nodes) -> None:
    labels = _knowledge_labels()
    spec_nodes = _knowledge_spec(nodes, labels)
    choice = _select_node(spec_nodes, f"knowledge-{investigation_id}")
    selected = next(node for node in nodes if node["id"] == choice)
    category = labels.get(selected["epistemic_state"], selected["epistemic_state"])
    st.markdown(f"**{category}**")
    st.write(selected["label"])
    st.caption(selected.get("note") or "No origin note was stored.")
    st.caption(
        f"Basis: {selected.get('basis') or 'recorded'}. "
        f"Confirmed: {bool(selected.get('confirmed'))}. Inferred: {bool(selected.get('inferred'))}."
    )
    if selected["epistemic_state"] == "frontier":
        st.caption("A frontier is an unresolved profile interest. It is not proof of a knowledge gap the user failed.")
        _frontier_action(api, investigation_id, selected["label"])
    elif selected["epistemic_state"] == "encountered":
        st.caption("This concept was presented in retrieved material. Exposure is not mastery and is not a prior.")


def _frontier_action(api, investigation_id, label) -> None:
    try:
        checkpoints = _get(api, f"/api/exploration/investigations/{investigation_id}/checkpoints")
    except requests.RequestException as exc:
        st.caption(f"Could not check checkpoints for this frontier: {exc}")
        return
    if not checkpoints:
        st.caption("This frontier has no checkpoint on the investigation, so it was not forked.")
        return
    st.button(
        "Investigate this frontier",
        on_click=_branch_from_frontier,
        args=(api, investigation_id, checkpoints[-1]["id"], label),
    )


def _assertion_form(api, investigation_id, profile_id) -> None:
    with st.form("knowledge_assertion"):
        subject = st.text_input("Subject")
        predicate = st.text_input("Predicate", value="related_to")
        obj = st.text_input("Object")
        text = st.text_input("Statement")
        state = st.selectbox("Epistemic state", ["known", "interested", "uncertain", "frontier"])
        submitted = st.form_submit_button("Record my confirmation")
    if not submitted:
        return
    if not subject.strip():
        st.error("A confirmation needs a subject.")
        return
    try:
        _post(api, "/api/exploration/profile/knowledge-assertions", {
            "profile_id": profile_id or "profile_unspecified",
            "investigation_id": investigation_id,
            "subject": subject.strip(),
            "predicate": predicate.strip() or "related_to",
            "object": obj.strip(),
            "text": text.strip() or subject.strip(),
            "epistemic_state": state,
            "basis": "user_confirmation",
        })
    except requests.RequestException as exc:
        st.error(f"Could not record the assertion: {exc}")
        return
    st.session_state["lantern_notice"] = "Recorded an explicit assertion. It is confirmed only because you submitted it."
    st.rerun(scope="app")


def _inspector(api, node, trace, checkpoints, investigation_id) -> None:
    payload = node.get("payload") or {}
    status = node.get("epistemic_status") or "unknown"
    st.markdown(f"**{node.get('type')}** · epistemic status: `{status}`")
    if node.get("verification_basis") == "none":
        st.caption("This node has no verification basis. A score on it is not evidence that the claim is true.")
    else:
        basis = str(node.get("verification_basis") or "none").replace("_", " ")
        st.caption(f"Status comes from {basis}, not from attention or knowledge value.")
    if payload.get("unresolved") or status == "unresolved":
        st.warning("Unresolved stop. This is not a verified answer, and it is not successful convergence.")
    kind = node["type"]
    if kind == "search":
        _show_search(payload)
    elif kind == "retrieval":
        _show_table(payload.get("pages") or [], "No pages were recorded for this retrieval.")
    elif kind == "ranking":
        st.caption("Attention and knowledge value are ranking signals. A missing bridge stays unknown.")
        _show_table(payload.get("candidates") or [], "No candidates were recorded on this ranking.")
    elif kind == "evidence":
        _show_evidence(payload)
    elif kind == "evidence_group":
        members = payload.get("members") or []
        st.caption(f"{payload.get('count') or len(members)} passages stay attached to this group. Expand the group to inspect each source.")
        for member in members:
            member_payload = member.get("payload") or {}
            st.write(member.get("label") or "Passage")
            st.caption(
                f"{member_payload.get('origin_kind') or 'unknown'} · "
                f"{member_payload.get('document_id') or 'no document id'} · "
                f"{member.get('epistemic_status') or 'unknown'}"
            )
    elif kind == "convergence":
        _show_convergence(payload)
    elif kind == "checkpoint":
        _checkpoint_panel(api, payload, checkpoints, investigation_id, trace["question"])
    elif kind == "ingest":
        st.caption("These documents were ingested as a corpus. This event is not a search.")
        _show_table(payload.get("documents") or [], "No documents recorded.")
    elif kind == "blocked":
        st.write(payload.get("blocker") or "Blocked. No results were invented.")
    elif kind == "extraction":
        st.write(payload.get("blocker") or "Extraction ran.")
        st.caption(f"Passages recorded: {len(payload.get('passages') or [])}.")


def _show_search(payload: dict) -> None:
    st.write(f"Query: {payload.get('query')}")
    st.write(f"Providers: {', '.join(payload.get('providers') or []) or 'unknown'}")
    st.write(f"Network: {payload.get('network')}")
    _show_table(payload.get("results") or [], "This search event recorded no returned results.")


def _show_table(rows: list, empty: str) -> None:
    if rows:
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.caption(empty)


def _show_evidence(payload: dict) -> None:
    st.write(payload.get("claim_text") or "No claim text recorded.")
    st.write(f"Passage: {payload.get('passage') or 'No passage recorded.'}")
    st.write(
        f"Origin: {payload.get('origin_kind') or 'unknown'} · "
        f"origin id: {payload.get('origin_id') or 'unknown'} · "
        f"provider: {payload.get('provider') or 'unknown'}"
    )
    st.write(f"Stances: {', '.join(payload.get('stances') or []) or 'none recorded'}")
    used = payload.get("used_by_relationship_ids") or []
    st.write(f"Used by relationships: {', '.join(used) or 'none recorded'}")
    if payload.get("relationships"):
        st.dataframe(pd.DataFrame(payload["relationships"]), use_container_width=True, hide_index=True)


def _show_convergence(payload: dict) -> None:
    st.write(f"Source: {payload.get('decision_source') or 'unknown'}")
    st.write(f"Stop reason: {payload.get('stop_reason') or 'none recorded'}")
    st.write(payload.get("rationale") or "No rationale recorded.")
    alternatives = payload.get("alternatives") or []
    if alternatives:
        st.markdown("**Alternatives considered**")
        st.dataframe(pd.DataFrame(alternatives), use_container_width=True, hide_index=True)
    else:
        st.caption("No alternative actions were recorded on this decision.")
    if payload.get("unresolved_questions"):
        st.markdown("**Unanswered questions**")
        for text in payload["unresolved_questions"]:
            st.write(f"- {text}")


def _checkpoint_panel(api, payload, checkpoints, investigation_id, question) -> None:
    checkpoint_id = payload.get("checkpoint_id")
    st.write(payload.get("summary") or "Checkpoint")
    if payload.get("inherited"):
        st.info("This branch inherited that checkpoint. The parent investigation was not modified.")
        inherited = payload.get("inherited_decision") or {}
        if inherited:
            st.caption(f"Inherited decision source: {inherited.get('decision_source') or 'unknown'}")
            st.write(inherited.get("rationale") or "")
    if payload.get("open_questions"):
        st.markdown("**Open questions at this checkpoint**")
        for text in payload["open_questions"]:
            st.write(f"- {text}")
    stored = next((item for item in checkpoints if item["id"] == checkpoint_id), None)
    if stored and st.session_state.get("lantern_checkpoint_view") == checkpoint_id:
        state = stored.get("state_json") or {}
        st.info("Showing the saved checkpoint snapshot. This did not change history.")
        if state.get("question") and state.get("question") != question:
            st.error("This snapshot's question does not match the investigation on screen.")
        else:
            st.caption(f"Snapshot question: {state.get('question') or question}")
        st.write(f"Status then: {state.get('status')} · stop: {state.get('stop_reason') or 'none'}")
        st.write(state.get("decision_rationale") or "No decision rationale stored on the snapshot.")
    if not checkpoint_id:
        return
    st.caption("Branch actions for this checkpoint are at the top of the inspector.")


def _map(trace, nodes, *, edges, kind, title, subtitle, selected_id=None, graph_key="", layout="dag") -> None:
    spec = {
        "kind": kind,
        "layout": layout,
        "title": title,
        "subtitle": subtitle,
        "selected_id": selected_id,
        "graph_key": graph_key,
        "viewport": st.session_state.get(f"lantern-viewport-{graph_key}"),
        "incomplete": bool(trace.get("incomplete")),
        "incomplete_reason": trace.get("incomplete_reason"),
        "nodes": [
            {
                "id": node["id"],
                "type": node["type"],
                "label": node.get("label") or node["type"],
                "kicker": node.get("kicker") or node["type"],
                "epistemic_status": node.get("epistemic_status") or "unknown",
            }
            for node in nodes
        ],
        "edges": [
            {"id": edge["id"], "source": edge["source"], "target": edge["target"], "kind": edge.get("kind") or "sequence"}
            for edge in edges
        ],
    }
    picked = _COMPONENT(spec=spec, key=f"lantern-map-{kind}", default=None)
    if isinstance(picked, dict) and picked.get("viewport"):
        st.session_state[f"lantern-viewport-{graph_key}"] = picked["viewport"]
    node_id = picked.get("node_id") if isinstance(picked, dict) else None
    if node_id and node_id != st.session_state.get("lantern_map_applied"):
        st.session_state["lantern_map_applied"] = node_id
        st.session_state["lantern_force_node"] = node_id


def _select_node(nodes, investigation_id):
    ids = [node["id"] for node in nodes]
    labels = {node["id"]: f"{node['type']} · {node['label']}" for node in nodes}
    widget_key = f"lantern-node-{investigation_id}"
    forced = st.session_state.pop("lantern_force_node", None)
    if forced in ids:
        st.session_state[widget_key] = forced
    elif st.session_state.get(widget_key) not in ids:
        st.session_state[widget_key] = ids[0]
    return st.selectbox(
        "Inspect a recorded node",
        ids,
        format_func=lambda item: labels[item],
        key=widget_key,
    )


def _artifact_table(notes) -> None:
    if not notes:
        return
    st.caption("Candidates are labeled by recorded activity. A high score does not verify the source.")
    st.dataframe(pd.DataFrame([
        {
            "title": note.get("title"),
            "activity": note.get("activity"),
            "origin": note.get("origin_kind") or "unknown",
            "bridge": note.get("bridge_trigger") or note.get("bridge_status") or "unknown",
            "attention": note.get("attention_score"),
            "knowledge value": note.get("knowledge_value_score"),
            "epistemic status": note.get("epistemic_status"),
            "verified": note.get("verified"),
        }
        for note in notes
    ]), use_container_width=True, hide_index=True)


def _trace_subtitle(trace) -> str:
    return (
        f"Recorded searches {trace.get('search_event_count', 0)}, "
        f"fetches {trace.get('fetch_event_count', 0)}, "
        f"LLM events {trace.get('llm_event_count', 0)}."
    )


def _family_ids(root, branches, current) -> list[str]:
    ordered = []
    for item in [root, current]:
        if item and item not in ordered:
            ordered.append(item)
    for branch in branches:
        child = branch.get("child_investigation_id")
        if child and child not in ordered:
            ordered.append(child)
    return ordered


def _origin(api: str, investigation_id: str, branches: list) -> str:
    current = investigation_id
    seen = set()
    current_branches = branches
    for _ in range(8):
        if current in seen:
            break
        seen.add(current)
        parent = next(
            (branch.get("parent_investigation_id") for branch in current_branches if branch.get("child_investigation_id") == current),
            None,
        )
        if not parent or parent == current:
            return current
        current_branches = _get(api, f"/api/exploration/investigations/{parent}/branches")
        current = parent
    return current


def _investigation_label(api, investigation_id, current_id, current_question) -> str:
    if investigation_id == current_id:
        return f"{current_question} ({investigation_id[-6:]})"
    try:
        body = _get(api, f"/api/exploration/investigations/{investigation_id}")
        question = body["investigation"]["question"]
    except requests.RequestException:
        question = investigation_id
    return f"{question} ({investigation_id[-6:]})"


def _branch(api, investigation_id, checkpoint_id, intervention, objective, max_searches, constraints=None) -> None:
    if constraints is None:
        objective = st.session_state.get(f"objective-{checkpoint_id}", objective) or objective
        max_searches = int(st.session_state.get(f"searches-{checkpoint_id}", max_searches) or max_searches)
        constraints = {"max_searches": max_searches}
    else:
        constraints = {key: value for key, value in constraints.items() if value is not None}
        constraints["max_searches"] = int(max_searches)
    billable = intervention in {"challenge_evidence", "continue"}
    st.session_state["lantern_branch_state"] = {
        "status": "pending",
        "message": "Creating the child lantern. The parent is left unchanged.",
        "billable": billable,
    }
    try:
        branch = _post(api, f"/api/exploration/investigations/{investigation_id}/branches", {
            "from_checkpoint_id": checkpoint_id,
            "objective": objective,
            "intervention_type": intervention,
            "constraints": constraints,
        })
        if billable:
            _post(api, f"/api/exploration/branches/{branch['id']}/resume")
        child = branch["child_investigation_id"]
        label = {"fork": "Forked", "challenge_evidence": "Challenged", "continue": "Continued"}[intervention]
        cost = " A search ran on the child." if billable else " No new search ran."
        message = f"{label} from {checkpoint_id}. Child {child}.{cost} The parent investigation was not modified."
        st.session_state["lantern_branch_state"] = {"status": "completed", "message": message, "billable": billable}
        st.session_state["lantern_notice"] = message
        _remember_and_open(api, child)
    except requests.RequestException as exc:
        message = f"Branch failed: {exc}"
        st.session_state["lantern_branch_state"] = {"status": "failed", "message": message, "billable": billable}
        st.session_state["lantern_notice"] = message


def _branch_from_frontier(api, investigation_id, checkpoint_id, label) -> None:
    _branch(api, investigation_id, checkpoint_id, "fork", f"Investigate the unresolved frontier: {label}", 1)


def _view_checkpoint(checkpoint_id: str) -> None:
    st.session_state["lantern_checkpoint_view"] = checkpoint_id


def _load_profile(api: str) -> None:
    try:
        export = _post(api, "/api/exploration/fixtures/profile")
    except requests.RequestException as exc:
        st.session_state["lantern_notice"] = f"Profile fixture failed: {exc}"
        return
    st.session_state["export"] = export
    st.session_state["ran_mode"] = "profile"
    st.session_state["lantern_root"] = export["investigation"]["id"]
    st.session_state["lantern_family"] = [export["investigation"]["id"]]
    st.session_state["lantern_notice"] = "Loaded the offline profile investigation. It did not search the web."
    st.query_params["investigation"] = export["investigation"]["id"]
    st.rerun(scope="app")


def _open_investigation(api: str, investigation_id: str, *, keep_family: bool) -> None:
    try:
        export = _get(api, f"/api/exploration/investigations/{investigation_id}")
    except requests.RequestException as exc:
        st.session_state["lantern_notice"] = f"Could not open {investigation_id}: {exc}"
        return
    if keep_family:
        _remember(investigation_id)
    st.session_state["export"] = export
    st.session_state["lantern_selected"] = None
    st.session_state["lantern_map_applied"] = None
    st.session_state["lantern_checkpoint_view"] = None
    st.session_state["lantern_family_choice"] = investigation_id
    st.query_params["investigation"] = investigation_id
    st.rerun(scope="app")


def _remember_and_open(api: str, investigation_id: str) -> None:
    _remember(investigation_id)
    _open_investigation(api, investigation_id, keep_family=True)


def _remember(investigation_id: str) -> None:
    family = list(st.session_state.get("lantern_family") or [])
    if investigation_id not in family:
        family.append(investigation_id)
    st.session_state["lantern_family"] = family


def _get(api: str, path: str):
    response = requests.get(f"{api}{path}", timeout=120)
    response.raise_for_status()
    return response.json()


def _post(api: str, path: str, body: dict | None = None):
    response = requests.post(f"{api}{path}", json=body or {}, timeout=300)
    response.raise_for_status()
    return response.json()
