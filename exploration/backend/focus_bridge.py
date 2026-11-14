"""Translate the exploration contract into the focus ranker and back.

``focus/focus_attention.py`` is the intent-anchored selector. It ranks passages
sequentially and may label one ``investigate``. Exploration asks whether to stop
or run one more search. This module is only that translation. It does not score
query attention, it does not verify quotes, and it does not call a provider.

``decision_source`` is not set here. The convergence client records
``convergence`` only when this body is actually consumed. A failed handoff stays
``fallback``.
"""

from __future__ import annotations

from datetime import date, datetime

from exploration.backend.attention import REFERENCE_DATE
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
    # No embedder: lexical scoring only, so this handoff cannot download a model.
    model = FocusAttentionModel(
        request.original_question,
        unresolved_questions=tuple(question.text for question in request.open_questions),
        now=REFERENCE_DATE,
    )
    if model.intent != request.original_question.strip():
        raise ValueError("focus intent drifted from the original investigation question")
    decisions = model.rank(passages_from_request(request))
    investigate = [item for item in decisions if item.action == "investigate"]
    archive_ids = [item.passage.id for item in decisions if item.action == "archive"]
    include_ids = [item.passage.id for item in investigate]
    pending = [action for action in request.proposed_actions if not action.already_executed]
    # One search approval. Focus's own batch cap cannot raise the exploration budget.
    if investigate and pending and request.budget.remaining_searches > 0:
        action = max(pending, key=lambda item: (item.utility, item.id))
        names = ", ".join(item.passage.id for item in investigate)
        return {
            "investigation_id": request.investigation_id,
            "approved_action": action.model_dump(mode="json"),
            "stop": False,
            "stop_reason": None,
            "rationale": (
                f"Focus routed {names} to investigate. "
                f"Approved the unused search action {action.id}. "
                "Investigation is not factual verification."
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
    elif request.open_questions:
        reason = "unresolved_uncertainty"
        detail = (
            "Focus marked candidates for consideration and did not request another search. "
            "Consideration is not verification."
        )
    else:
        reason = "evidence_sufficient"
        detail = (
            "Focus kept the candidates inside the current boundary and did not request another search. "
            "Consideration is not verification."
        )
    summary = "; ".join(f"{item.passage.id}={item.action} ({item.reason})" for item in decisions) or "no candidates"
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


class _InProcessResponse:
    """Minimal stand-in for an httpx response, so the orchestrator's ``post``
    hook can reach focus in the same process without a running HTTP server.
    """

    def __init__(self, body: dict) -> None:
        self._body = body

    def raise_for_status(self) -> None:  # pragma: no cover - always ok here
        return None

    def json(self) -> dict:
        return self._body


def focus_post(url: str, *, json: dict, timeout=None) -> _InProcessResponse:
    """Route the convergence request straight through focus, in process.

    Matches the call shape ``evaluate_controller`` uses for ``httpx.post``:
    positional URL, keyword ``json`` body, optional ``timeout``. The URL and
    timeout are ignored because no socket is opened. This is how a live
    pipeline run uses the focus ranker as the convergence controller.
    """

    return _InProcessResponse(focus_http_response(json))


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
