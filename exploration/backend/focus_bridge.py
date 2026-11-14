"""Translate the exploration contract into Sam Hubler's focus ranker and back.

``focus/focus_attention.py`` is the convergence algorithm. It ranks passages.
Exploration asks whether to stop or run one more search. This module is only
that translation. It does not score evidence itself and it does not verify quotes.
"""

from __future__ import annotations

from datetime import date, datetime

from focus.focus_attention import FocusAttentionModel, Passage

from shared.contracts import ConvergenceEvaluateRequest

_STOPS = {
    "evidence_sufficient",
    "low_expected_value",
    "no_useful_actions",
    "budget_exhausted",
    "unresolved_uncertainty",
}


def passages_from_request(request: ConvergenceEvaluateRequest) -> list[Passage]:
    passages: list[Passage] = []
    for candidate in request.candidates:
        passages.append(
            Passage(
                id=candidate.id,
                text=candidate.snippet or candidate.title,
                url=candidate.url,
                title=candidate.title,
                providers=tuple(candidate.providers),
                published_at=_published(candidate.publish_date),
            )
        )
    return passages


def evaluate_with_focus(request: ConvergenceEvaluateRequest) -> dict:
    """Return a JSON body ``decision_from_controller`` already accepts."""
    if request.budget.remaining_searches <= 0:
        return _stopped(
            request,
            "budget_exhausted",
            "Focus controller declined another search because no search budget remains.",
        )
    model = FocusAttentionModel(
        request.original_question,
        unresolved_questions=tuple(question.text for question in request.open_questions),
    )
    decisions = model.rank(passages_from_request(request))
    investigate = [item for item in decisions if item.action == "investigate"]
    archive_ids = [item.passage.id for item in decisions if item.action == "archive"]
    include_ids = [item.passage.id for item in investigate]
    pending = [action for action in request.proposed_actions if not action.already_executed]
    if investigate and pending:
        action = max(pending, key=lambda item: (item.utility, item.id))
        names = ", ".join(item.passage.id for item in investigate)
        return {
            "investigation_id": request.investigation_id,
            "approved_action": action.model_dump(mode="json"),
            "stop": False,
            "stop_reason": None,
            "rationale": (
                f"Focus routed {names} to investigate. "
                f"Approved the unused search action {action.id}."
            ),
            "include_document_ids": include_ids,
            "archive_document_ids": archive_ids,
        }
    if investigate:
        reason = "unresolved_uncertainty"
        detail = "Focus routed passages to investigate, and no unused search action remains."
    elif not decisions:
        reason = "no_useful_actions"
        detail = "Focus received no candidates to rank."
    elif all(item.action == "archive" for item in decisions):
        reason = "low_expected_value"
        detail = "Focus archived every candidate."
    else:
        reason = "evidence_sufficient"
        detail = "Focus kept the candidates inside the current boundary and did not request another search."
    summary = "; ".join(f"{item.passage.id}={item.action}" for item in decisions) or "no candidates"
    return _stopped(
        request,
        reason,
        f"{detail} Decisions: {summary}.",
        include_ids=include_ids,
        archive_ids=archive_ids,
    )


def focus_http_response(payload: dict) -> dict:
    request = ConvergenceEvaluateRequest.model_validate(payload)
    body = evaluate_with_focus(request)
    if body.get("stop_reason") not in _STOPS and body.get("stop"):
        raise ValueError("focus bridge emitted a stop reason exploration does not accept")
    return body


def _stopped(
    request: ConvergenceEvaluateRequest,
    reason: str,
    rationale: str,
    *,
    include_ids: list[str] | None = None,
    archive_ids: list[str] | None = None,
) -> dict:
    return {
        "investigation_id": request.investigation_id,
        "approved_action": None,
        "stop": True,
        "stop_reason": reason,
        "rationale": rationale,
        "include_document_ids": include_ids or [],
        "archive_document_ids": archive_ids or [],
    }


def _published(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError:
        pass
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None
