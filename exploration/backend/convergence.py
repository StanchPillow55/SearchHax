"""Client for the convergence controller.

Exploration POSTs candidates, open questions, and budget. It records
``decision_source=convergence`` only when the endpoint returns a usable
decision. Any connection, HTTP, or schema failure uses the labeled fallback
and does not pretend the controller answered.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import httpx

from shared.contracts import (
    ConvergenceDecision,
    ConvergenceEvaluateRequest,
    InvestigationAction,
    InvestigationBudget,
    StopReason,
    UnresolvedQuestion,
)

from exploration.backend.config import convergence_url
from exploration.backend.planner import fallback_decision

PostFn = Callable[..., Any]
_STOPS: set[str] = {
    "evidence_sufficient",
    "low_expected_value",
    "no_useful_actions",
    "budget_exhausted",
    "unresolved_uncertainty",
}


def evaluate_controller(
    request: ConvergenceEvaluateRequest,
    *,
    followups_executed: int,
    url: str | None = None,
    post: PostFn | None = None,
) -> ConvergenceDecision:
    target = url or convergence_url()
    sender = post or httpx.post
    try:
        response = sender(
            target,
            json=request.model_dump(mode="json"),
            timeout=httpx.Timeout(2.0, connect=0.5),
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("convergence response was not an object")
        return decision_from_controller(payload, request.investigation_id)
    except Exception as exc:
        return fallback_decision(
            investigation_id=request.investigation_id,
            questions=request.open_questions,
            actions=request.proposed_actions,
            budget=request.budget,
            followups_executed=followups_executed,
            error_type=type(exc).__name__,
        )


def decision_from_controller(payload: dict[str, Any], investigation_id: str) -> ConvergenceDecision:
    data = dict(payload)
    if "approved_action" not in data and isinstance(data.get("action"), dict):
        data["approved_action"] = data["action"]
    action = None
    if isinstance(data.get("approved_action"), dict):
        action = InvestigationAction.model_validate(data["approved_action"])
    stop_reason = data.get("stop_reason")
    if stop_reason not in _STOPS:
        stop_reason = None
    stop = _as_bool(data.get("stop", action is None))
    rationale = str(data.get("rationale") or "").strip()
    if not rationale:
        raise ValueError("convergence response missing rationale")
    return ConvergenceDecision(
        investigation_id=str(data.get("investigation_id") or investigation_id),
        approved_action=None if stop else action,
        stop=stop,
        stop_reason=stop_reason if stop else None,
        rationale=rationale,
        decision_source="convergence",
        include_document_ids=list(data.get("include_document_ids") or []),
        archive_document_ids=list(data.get("archive_document_ids") or []),
    )


def _as_bool(value: Any) -> bool:
    """Parse a JSON stop flag. The string "false" is not a stop."""
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, (int, float)) and value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        text = value.strip().lower()
        if text in {"true", "1", "yes"}:
            return True
        if text in {"false", "0", "no", ""}:
            return False
    raise ValueError(f"convergence stop flag is not a boolean: {value!r}")


def build_request(
    *,
    investigation_id: str,
    question: str,
    questions: list[UnresolvedQuestion],
    candidates,
    actions: list[InvestigationAction],
    budget: InvestigationBudget,
    usage,
) -> ConvergenceEvaluateRequest:
    return ConvergenceEvaluateRequest(
        investigation_id=investigation_id,
        original_question=question,
        open_questions=questions,
        candidates=candidates,
        proposed_actions=actions,
        budget=budget,
        usage=usage,
    )
