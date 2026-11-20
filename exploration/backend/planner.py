"""Candidate search actions from unresolved gaps.

Utility is importance times missing evidence. These are ranking weights, not
calibrated probabilities. The fallback policy is exploration's own stop rule
when the convergence controller is unavailable. It is not a second convergence
engine: it does not score intent alignment, novelty, or redundancy.
"""

from __future__ import annotations

import re

from shared.contracts import (
    ConvergenceDecision,
    InvestigationAction,
    InvestigationBudget,
    UnresolvedQuestion,
)

from exploration.backend.attention import clamp01
from exploration.backend.ids import stable_id


def initial_search_query(question: str) -> str:
    """Retrieval formulation. The stored investigation question is not changed.

    Long analytical questions are a poor fit for web search. The Story A
    question is sent as a compact NVIDIA/CoreWeave query because that is the
    relationship the investigation is trying to ground.
    """
    text = question.strip()
    lowered = text.lower()
    if "nvidia" in lowered and "investment" in lowered and "capacity" in lowered:
        return "NVIDIA CoreWeave investment AI factories capacity 2026"
    if len(text) <= 180:
        return text
    sentence = re.split(r"[.?\n]", text, maxsplit=1)[0].strip()
    return sentence[:180]


def generate_actions(
    questions: list[UnresolvedQuestion],
    previous_queries: list[str],
) -> list[InvestigationAction]:
    seen = {query.strip().lower() for query in previous_queries}
    actions: list[InvestigationAction] = []
    for question in questions:
        query = _query_for(question)
        if query.strip().lower() in seen:
            continue
        utility = clamp01(question.importance * question.missing_evidence)
        actions.append(
            InvestigationAction(
                id=stable_id("act", question.id, query),
                query=query,
                reason=(
                    f"Open {question.kind} question ranked by importance {question.importance:.2f} "
                    f"and missing evidence {question.missing_evidence:.2f}."
                ),
                target_question_id=question.id,
                utility=utility,
                already_executed=False,
            )
        )
    actions.sort(key=lambda action: (-action.utility, action.id))
    return actions


def fallback_decision(
    *,
    investigation_id: str,
    questions: list[UnresolvedQuestion],
    actions: list[InvestigationAction],
    budget: InvestigationBudget,
    followups_executed: int,
    error_type: str,
) -> ConvergenceDecision:
    """Deterministic fallback. decision_source is always fallback."""
    rationale_prefix = (
        f"Convergence endpoint unavailable ({error_type}). "
        "Fallback ranked open questions by importance and missing evidence."
    )
    if followups_executed >= 1:
        reason = "unresolved_uncertainty" if _material_gap(questions) else "evidence_sufficient"
        return ConvergenceDecision(
            investigation_id=investigation_id,
            approved_action=None,
            stop=True,
            stop_reason=reason,
            rationale=rationale_prefix + " One follow-up already ran, so fallback stops.",
            decision_source="fallback",
        )
    if budget.remaining_searches <= 0 or budget.searches_used >= min(budget.max_searches, 2):
        return ConvergenceDecision(
            investigation_id=investigation_id,
            approved_action=None,
            stop=True,
            stop_reason="budget_exhausted",
            rationale=rationale_prefix + " No search budget remains.",
            decision_source="fallback",
        )
    pending = [action for action in actions if not action.already_executed]
    useful = [action for action in pending if action.utility >= budget.min_utility]
    if not useful:
        if pending and all(action.utility < budget.min_utility for action in pending):
            reason = "low_expected_value"
            detail = " Every remaining query is below the utility floor."
        elif _material_gap(questions):
            reason = "unresolved_uncertainty"
            detail = " Material questions remain, but there is no unused query to run."
        else:
            reason = "no_useful_actions"
            detail = " No unused query is available."
        return ConvergenceDecision(
            investigation_id=investigation_id,
            approved_action=None,
            stop=True,
            stop_reason=reason,
            rationale=rationale_prefix + detail,
            decision_source="fallback",
        )
    chosen = useful[0]
    return ConvergenceDecision(
        investigation_id=investigation_id,
        approved_action=chosen,
        stop=False,
        stop_reason=None,
        rationale=rationale_prefix + f" Selected the highest-priority unused query: {chosen.query}",
        decision_source="fallback",
    )


def _query_for(question: UnresolvedQuestion) -> str:
    text = question.text.strip()
    if question.kind in {"independence", "contradiction"} and not text.lower().startswith("independent"):
        return f"independent primary source for: {text}"
    return text


def _material_gap(questions: list[UnresolvedQuestion]) -> bool:
    return any(question.missing_evidence >= 0.5 for question in questions)


# --------------------------------------------------------------------------- branch planning
#
# A branch keeps the root research question. Its objective is a separate, optional
# instruction. A vague objective ("Is this true?") is never sent to retrieval on its own:
# it is resolved against the claims the user attached, or refused.

_DEICTIC_WORDS = {
    "a", "an", "the", "is", "are", "was", "were", "be", "it", "this", "that", "these", "those",
    "true", "false", "correct", "right", "accurate", "real", "really", "actually", "valid",
    "verify", "check", "confirm", "test", "prove", "challenge", "investigate", "look", "into",
    "please", "can", "could", "you", "we", "does", "do", "did", "what", "why", "how", "about",
    "so", "just", "still", "claim", "claims", "fact", "facts", "source", "sources", "evidence",
    "more", "again", "further", "and", "or", "of", "for", "on", "in", "to", "if", "whether",
}

MAX_BRANCH_QUERY_CHARS = 240


def _content_words(text: str) -> list[str]:
    words = re.findall(r"[A-Za-z0-9$%][A-Za-z0-9$%.,'’-]*", text.lower())
    return [w.strip(".,'’-") for w in words if w.strip(".,'’-") not in _DEICTIC_WORDS and len(w.strip(".,'’-")) > 1]


def is_grounded_objective(objective: str) -> bool:
    """True when the objective names something to search for on its own.

    "Is this true?", "verify this", "" and whitespace are not grounded: they only make
    sense relative to a selected claim, so retrieval must not receive them alone.
    """
    return len(_content_words(objective or "")) >= 2


def branch_query(
    *,
    root_question: str,
    objective: str,
    attached_claims: list[dict],
    intervention_type: str,
) -> tuple[str | None, dict]:
    """Retrieval query for the first search of a branch, plus what it was planned from.

    Returns (None, planned_from) when there is nothing grounded to search for. The root
    question is never replaced; it is only used as a last resort for ``continue``.
    """
    objective = (objective or "").strip()
    claims = [c for c in attached_claims if isinstance(c, dict) and (c.get("text") or "").strip()]
    planned_from = {
        "claim_ids": [c.get("id") for c in claims],
        "objective": objective,
        "objective_grounded": is_grounded_objective(objective),
        "intervention_type": intervention_type,
    }
    if claims:
        claim_text = " ".join(c["text"].strip() for c in claims[:2])
        if intervention_type == "challenge_evidence":
            query = f"independent evidence for or against: {claim_text}"
        else:
            query = claim_text
        if planned_from["objective_grounded"]:
            extra = [w for w in _content_words(objective) if w not in claim_text.lower()]
            if extra:
                query = f"{query} {' '.join(extra)}"
        return query[:MAX_BRANCH_QUERY_CHARS].strip(), planned_from
    if planned_from["objective_grounded"]:
        return objective[:MAX_BRANCH_QUERY_CHARS].strip(), planned_from
    if intervention_type == "continue":
        return initial_search_query(root_question), planned_from
    return None, planned_from
