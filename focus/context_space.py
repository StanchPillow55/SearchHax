"""Evidence context space.

Two callers share this module. The standalone TraceFork app passes focus
decisions it just computed. The FrontierGraph page passes coordinates that a
checkpoint already recorded. This module does not rank, search, or rewrite
those records.

Axes stay interpretable: intent alignment, novelty, and unresolved-question
alignment. PCA is not a coordinate system here.
"""

from __future__ import annotations

from dataclasses import dataclass


AXIS_X = "Intent alignment"
AXIS_Y = "Novelty"
AXIS_Z = "Unresolved-question alignment"

ACTION_COLORS = {
    "consider": "#2ca02c",
    "investigate": "#ff7f0e",
    "archive": "#7f7f7f",
    "recorded": "#4c78a8",
}
ROLE_COLORS = {
    "shared": "#4c78a8",
    "new": "#f2c14e",
    "conflict": "#e45756",
}


@dataclass(frozen=True)
class EvidencePoint:
    evidence_id: str
    investigation_id: str
    branch_id: str
    document_id: str | None
    url: str
    title: str
    passage: str
    intent_alignment: float
    novelty: float
    unresolved_alignment: float
    action: str
    reason: str
    attention_score: float | None
    attention_relevance: float | None
    attention_gap: float | None
    knowledge_value_score: float | None
    knowledge_value_novelty: float | None
    bridge_trigger: str | None
    epistemic_status: str
    verification_basis: str
    relationships: tuple[dict, ...]
    provenance: dict | None
    convergence: dict | None
    activity: str
    compare_role: str | None = None


@dataclass(frozen=True)
class SpaceView:
    points: tuple[EvidencePoint, ...]
    checkpoint_id: str | None
    reason: str | None
    playback: bool
    search_event_count: int
    status: str | None
    stop_reason: str | None
    incomplete: bool
    incomplete_reason: str | None
    omitted: int
    decision_source: str | None


def figure_from_focus_decisions(decisions):
    """Same chart the standalone app showed inline, including axis names."""
    import pandas as pd
    import plotly.express as px

    rows = []
    for decision in decisions:
        passage = decision.passage
        score = decision.score
        rows.append(
            {
                "Source": passage.title or passage.text[:80],
                "Action": decision.action,
                "URL": passage.url,
                "Relevance": round(score.relevance, 3),
                "Novelty": round(score.novelty, 3),
                "Graph gap": round(score.graph_gap, 3),
                "Attention": round(score.attention, 3),
                "Evidence id": passage.id,
                AXIS_X: round(score.relevance, 3),
                AXIS_Y: round(score.novelty, 3),
                AXIS_Z: round(score.graph_gap, 3),
            }
        )
    figure = px.scatter_3d(
        pd.DataFrame(rows),
        x=AXIS_X,
        y=AXIS_Y,
        z=AXIS_Z,
        color="Action",
        hover_name="Source",
        hover_data=["URL", "Attention", "Relevance", "Novelty", "Graph gap"],
        custom_data=["Evidence id"],
        color_discrete_map={"consider": "#2ca02c", "investigate": "#ff7f0e", "archive": "#7f7f7f"},
        title="Evidence context space",
    )
    figure.update_traces(marker={"size": 8, "opacity": 0.86})
    figure.update_layout(margin={"l": 0, "r": 0, "t": 45, "b": 0}, legend_title_text="Policy action")
    return figure


def points_from_recorded(trace: dict, checkpoints: list[dict], checkpoint_id: str | None, investigation: dict | None = None) -> SpaceView:
    """Build the space from a saved checkpoint. Missing coordinates stay missing."""
    events = list(trace.get("events") or [])
    incomplete = bool(trace.get("incomplete"))
    incomplete_reason = trace.get("incomplete_reason")
    search_count = int(trace.get("search_event_count") or 0)
    status = (investigation or {}).get("status")
    stop_reason = (investigation or {}).get("stop_reason")
    decision_source = (investigation or {}).get("decision_source")
    if not events:
        return SpaceView(
            points=(),
            checkpoint_id=None,
            reason="No investigation events were recorded. No evidence points are drawn.",
            playback=False,
            search_event_count=0,
            status=status,
            stop_reason=stop_reason,
            incomplete=True,
            incomplete_reason=incomplete_reason or "No investigation events were recorded.",
            omitted=0,
            decision_source=decision_source,
        )
    chosen, playback = _choose_checkpoint(checkpoints, checkpoint_id)
    if playback and chosen is None:
        return SpaceView(
            points=(),
            checkpoint_id=checkpoint_id,
            reason="That checkpoint is not part of this investigation. No points were copied from another run.",
            playback=True,
            search_event_count=search_count,
            status=status,
            stop_reason=stop_reason,
            incomplete=incomplete,
            incomplete_reason=incomplete_reason,
            omitted=0,
            decision_source=decision_source,
        )
    if chosen is None:
        return SpaceView(
            points=(),
            checkpoint_id=None,
            reason="No checkpoint was recorded, so there is no policy space to show.",
            playback=False,
            search_event_count=search_count,
            status=status,
            stop_reason=stop_reason,
            incomplete=incomplete,
            incomplete_reason=incomplete_reason,
            omitted=0,
            decision_source=decision_source,
        )
    state = chosen.get("state_json") or {}
    status = state.get("status") or status
    stop_reason = state.get("stop_reason") or chosen.get("stop_reason") or stop_reason
    decision_source = state.get("decision_source") or decision_source
    recorded = state.get("policy_space")
    snapshot = state.get("snapshot") if isinstance(state.get("snapshot"), dict) else {}
    candidate_ids = [item.get("id") for item in snapshot.get("candidates") or [] if item.get("id")]
    if not isinstance(recorded, list):
        return SpaceView(
            points=(),
            checkpoint_id=chosen.get("id"),
            reason="This checkpoint has no recorded policy coordinates. They were not reconstructed.",
            playback=playback,
            search_event_count=search_count,
            status=status,
            stop_reason=stop_reason,
            incomplete=incomplete,
            incomplete_reason=incomplete_reason,
            omitted=len(candidate_ids),
            decision_source=decision_source,
        )
    points = tuple(
        _point_from_row(row, state, snapshot, trace)
        for row in recorded
        if _coordinates(row) is not None
    )
    plotted = {point.evidence_id for point in points}
    omitted = len([item for item in candidate_ids if item not in plotted])
    reason = None
    if not points:
        if candidate_ids:
            reason = "Candidates were recorded without policy coordinates. Nothing was plotted in their place."
        else:
            reason = "No evidence was recorded at this checkpoint."
    return SpaceView(
        points=points,
        checkpoint_id=chosen.get("id"),
        reason=reason,
        playback=playback,
        search_event_count=search_count,
        status=status,
        stop_reason=stop_reason,
        incomplete=incomplete,
        incomplete_reason=incomplete_reason,
        omitted=omitted,
        decision_source=decision_source,
    )


def latest_eligible_checkpoint(checkpoints: list[dict], evidence_id: str, document_id: str | None = None, url: str | None = None) -> dict | None:
    """Latest saved checkpoint that actually contains the evidence.

    A plotted point is not itself a place to resume.
    """
    matches = [
        checkpoint
        for checkpoint in checkpoints
        if _checkpoint_contains(checkpoint, evidence_id, document_id, url)
    ]
    if not matches:
        return None
    return max(matches, key=lambda item: (item.get("step") or 0, str(item.get("created_at") or ""), item.get("id") or ""))


def preview_ranking(points: tuple[EvidencePoint, ...] | list[EvidencePoint], weights: dict) -> list[tuple[str, float]]:
    """Reorder recorded coordinates. Does not write the new order back onto them."""
    intent = float(weights.get("intent", 1))
    novelty = float(weights.get("novelty", 1))
    unresolved = float(weights.get("unresolved", 1))
    knowledge = weights.get("knowledge_value")
    ranked = []
    for point in points:
        score = intent * point.intent_alignment + novelty * point.novelty + unresolved * point.unresolved_alignment
        if knowledge is not None and point.knowledge_value_score is not None:
            score += float(knowledge) * point.knowledge_value_score
        ranked.append((point.evidence_id, score))
    ranked.sort(key=lambda item: (-item[1], item[0]))
    return ranked


def compare_points(left: tuple[EvidencePoint, ...] | list[EvidencePoint], right: tuple[EvidencePoint, ...] | list[EvidencePoint], left_snapshot: dict | None = None, right_snapshot: dict | None = None) -> list[EvidencePoint]:
    """Mark shared, newly discovered, and conflicting evidence on the same axes."""
    left_keys = {_evidence_key(point): point for point in left}
    right_keys = {_evidence_key(point): point for point in right}
    left_claims = _claim_signatures(left_snapshot or {}, left)
    right_claims = _claim_signatures(right_snapshot or {}, right)
    compared = []
    for key in sorted(set(left_keys) | set(right_keys)):
        sides = []
        if key in left_keys:
            sides.append(left_keys[key])
        if key in right_keys:
            sides.append(right_keys[key])
        role = "new"
        if key in left_keys and key in right_keys:
            role = "conflict" if _claims_conflict(left_claims.get(key), right_claims.get(key)) else "shared"
        for point in sides:
            compared.append(_with_role(point, role))
    return compared


def component_spec(points: list[EvidencePoint] | tuple[EvidencePoint, ...], *, selected_id: str | None, camera: dict | None, title: str, color_by: str) -> dict:
    """Chart payload. Positions are the recorded coordinates, never preview weights."""
    grouped: dict[str, list[EvidencePoint]] = {}
    for point in points:
        if color_by == "role":
            label = point.compare_role or "shared"
            color = ROLE_COLORS.get(label, ACTION_COLORS["recorded"])
        else:
            label = point.action or "recorded"
            color = ACTION_COLORS.get(label, ACTION_COLORS["recorded"])
        grouped.setdefault(f"{label}|{color}", []).append(point)
    traces = []
    for key, group in grouped.items():
        label, color = key.split("|", 1)
        traces.append(
            {
                "name": label,
                "color": color,
                "x": [point.intent_alignment for point in group],
                "y": [point.novelty for point in group],
                "z": [point.unresolved_alignment for point in group],
                "text": [point.title or point.evidence_id for point in group],
                "evidence_id": [point.evidence_id for point in group],
                "investigation_id": [point.investigation_id for point in group],
                "branch_id": [point.branch_id for point in group],
                "size": [14 if point.evidence_id == selected_id else 8 for point in group],
            }
        )
    return {
        "title": title,
        "axis_x": AXIS_X,
        "axis_y": AXIS_Y,
        "axis_z": AXIS_Z,
        "selected_id": selected_id,
        "camera": camera,
        "traces": traces,
    }


def evidence_id_from_plotly_selection(selection) -> str | None:
    """Read an evidence id when a selection payload actually carries one.

    Streamlit's scatter click path does not. Callers still need the selector.
    """
    if selection is None:
        return None
    if isinstance(selection, dict) and "selection" in selection and "points" not in selection:
        selection = selection.get("selection")
    points = []
    if isinstance(selection, dict):
        points = selection.get("points") or []
    for point in points:
        if not isinstance(point, dict):
            continue
        custom = point.get("customdata")
        if isinstance(custom, str) and custom:
            return custom
        if isinstance(custom, dict) and custom.get("evidence_id"):
            return str(custom["evidence_id"])
        if isinstance(custom, (list, tuple)) and custom and isinstance(custom[0], str) and custom[0]:
            return custom[0]
    return None


def evidence_id_for_node(node: dict | None, points: list[EvidencePoint] | tuple[EvidencePoint, ...]) -> str | None:
    if not node or node.get("type") != "evidence":
        return None
    document_id = (node.get("payload") or {}).get("document_id")
    matches = [point for point in points if document_id and point.document_id == document_id]
    if len(matches) == 1:
        return matches[0].evidence_id
    return None


def node_id_for_evidence(evidence_id: str, nodes: list[dict], points: list[EvidencePoint] | tuple[EvidencePoint, ...]) -> str | None:
    point = next((item for item in points if item.evidence_id == evidence_id), None)
    if point is None or not point.document_id:
        return None
    for node in nodes:
        if node.get("type") != "evidence":
            continue
        if (node.get("payload") or {}).get("document_id") == point.document_id:
            return node.get("id")
    return None


def point_by_id(points: list[EvidencePoint] | tuple[EvidencePoint, ...], evidence_id: str | None) -> EvidencePoint | None:
    if not evidence_id:
        return None
    return next((point for point in points if point.evidence_id == evidence_id), None)


def _choose_checkpoint(checkpoints: list[dict], checkpoint_id: str | None) -> tuple[dict | None, bool]:
    if checkpoint_id:
        return next((item for item in checkpoints if item.get("id") == checkpoint_id), None), True
    if not checkpoints:
        return None, False
    return max(checkpoints, key=lambda item: (item.get("step") or 0, str(item.get("created_at") or ""), item.get("id") or "")), False


def _checkpoint_contains(checkpoint: dict, evidence_id: str, document_id: str | None, url: str | None) -> bool:
    state = checkpoint.get("state_json") or {}
    for row in state.get("policy_space") or []:
        if not isinstance(row, dict):
            continue
        if row.get("evidence_id") == evidence_id:
            return True
        if document_id and row.get("document_id") == document_id:
            return True
        if url and row.get("url") == url:
            return True
    snapshot = state.get("snapshot") if isinstance(state.get("snapshot"), dict) else {}
    for candidate in snapshot.get("candidates") or []:
        if not isinstance(candidate, dict):
            continue
        if candidate.get("id") == evidence_id:
            return True
        if document_id and candidate.get("document_id") == document_id:
            return True
        if url and candidate.get("url") == url:
            return True
    return False


def _coordinates(row: dict) -> tuple[float, float, float] | None:
    if not isinstance(row, dict) or not row.get("evidence_id"):
        return None
    try:
        return (float(row["intent_alignment"]), float(row["novelty"]), float(row["unresolved_alignment"]))
    except (KeyError, TypeError, ValueError):
        return None


def _point_from_row(row: dict, state: dict, snapshot: dict, trace: dict) -> EvidencePoint:
    intent, novelty, unresolved = _coordinates(row)
    document_id = row.get("document_id")
    relationships = tuple(
        {
            "id": item.get("id"),
            "predicate": item.get("predicate"),
            "subject": item.get("subject_name") or item.get("subject"),
            "object": item.get("object_name") or item.get("object"),
            "status": item.get("status"),
        }
        for item in snapshot.get("relationships") or []
        if isinstance(item, dict) and document_id and (item.get("document_id") == document_id or document_id in (item.get("source_document_ids") or []))
    )
    provenance = next(
        (item for item in snapshot.get("provenance") or [] if isinstance(item, dict) and item.get("document_id") == document_id),
        None,
    )
    epistemic, basis = _epistemic(relationships)
    decision = state.get("decision") if isinstance(state.get("decision"), dict) else None
    branch_id = row.get("branch_id") or trace.get("branch_id") or f"root:{row.get('investigation_id') or trace.get('investigation_id')}"
    activity = _activity(trace, row.get("evidence_id"))
    return EvidencePoint(
        evidence_id=str(row["evidence_id"]),
        investigation_id=str(row.get("investigation_id") or trace.get("investigation_id") or ""),
        branch_id=str(branch_id),
        document_id=document_id,
        url=row.get("url") or "",
        title=row.get("title") or "",
        passage=row.get("passage") or "",
        intent_alignment=intent,
        novelty=novelty,
        unresolved_alignment=unresolved,
        action=row.get("action") or "recorded",
        reason=row.get("reason") or "",
        attention_score=_optional_float(row.get("attention_score")),
        attention_relevance=_optional_float(row.get("attention_relevance")),
        attention_gap=_optional_float(row.get("attention_gap")),
        knowledge_value_score=_optional_float(row.get("knowledge_value_score")),
        knowledge_value_novelty=_optional_float(row.get("knowledge_value_novelty")),
        bridge_trigger=row.get("bridge_trigger"),
        epistemic_status=epistemic,
        verification_basis=basis,
        relationships=relationships,
        provenance=provenance,
        convergence={
            "decision_source": state.get("decision_source"),
            "stop_reason": state.get("stop_reason"),
            "rationale": state.get("decision_rationale") or (decision or {}).get("rationale"),
            "stop": (decision or {}).get("stop"),
            "unresolved": state.get("stop_reason") == "unresolved_uncertainty",
        },
        activity=activity,
    )


def _activity(trace: dict, evidence_id: str | None) -> str:
    for note in trace.get("artifact_notes") or []:
        if note.get("id") == evidence_id:
            return note.get("activity") or "unknown"
    return "unknown"


def _epistemic(relationships: tuple[dict, ...]) -> tuple[str, str]:
    if any(item.get("status") == "contradicted" for item in relationships):
        return "contradicted", "relationship_status"
    if any(item.get("status") == "supported" for item in relationships):
        return "supported", "relationship_status"
    return "unknown", "none"


def _evidence_key(point: EvidencePoint) -> str:
    if point.url:
        return "url:" + point.url.strip().lower()
    return "id:" + point.evidence_id


def _claim_signatures(snapshot: dict, points: list[EvidencePoint] | tuple[EvidencePoint, ...]) -> dict[str, frozenset]:
    by_document = {}
    for point in points:
        if point.document_id:
            by_document.setdefault(point.document_id, _evidence_key(point))
    signatures: dict[str, set] = {}
    for item in snapshot.get("relationships") or []:
        if not isinstance(item, dict):
            continue
        documents = [item.get("document_id"), *(item.get("source_document_ids") or [])]
        signature = (item.get("predicate"), item.get("object_name") or item.get("object"), item.get("status"))
        for document_id in documents:
            key = by_document.get(document_id)
            if key:
                signatures.setdefault(key, set()).add(signature)
    return {key: frozenset(value) for key, value in signatures.items()}


def _claims_conflict(left: frozenset | None, right: frozenset | None) -> bool:
    if not left or not right or left == right:
        return False
    return True


def _with_role(point: EvidencePoint, role: str) -> EvidencePoint:
    return EvidencePoint(**{**point.__dict__, "compare_role": role})


def _optional_float(value) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
