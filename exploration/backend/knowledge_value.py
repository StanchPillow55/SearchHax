"""Knowledge-value ranking for a static research profile.

U = 0.25*R + 0.25*N + 0.20*B + 0.20*I + 0.10*C

R is overlap with profile interests and goals. N is the share of passage
tokens that are not already in known claims. B is 1 only when a profile
interest and a DOMAIN_BRIDGES bridge term both occur and that bridge term is
outside the known claims. I is overlap with the unresolved interest. C is 1
only for a real contradiction of a known claim.

This is a heuristic. It is not a probability, not factual confidence, and not
the query-attention score A(q, p). A high U does not create a supported edge.
"""

from __future__ import annotations

import re
from typing import Mapping, Sequence

from shared.contracts import KnowledgeValue, ResearchProfile

from exploration.backend import attention as attention_module

WEIGHT_R = 0.25
WEIGHT_N = 0.25
WEIGHT_B = 0.20
WEIGHT_I = 0.20
WEIGHT_C = 0.10

_PREDICATE_CUES = {
    "invested_in": "invested in",
    "expansion_status": "capacity expansion is",
}


def _coverage(needles: set[str], haystack: set[str]) -> float:
    if not needles:
        return 0.0
    return attention_module.clamp01(len(needles & haystack) / len(needles))


def _known_tokens(profile: ResearchProfile) -> set[str]:
    tokens: set[str] = set()
    for claim in profile.known_claims:
        tokens |= attention_module.tokenize(f"{claim.subject} {claim.predicate} {claim.object} {claim.text}")
    return tokens


def _interest_token_map(profile: ResearchProfile) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for interest in profile.interests:
        for token in attention_module.tokenize(interest):
            mapping.setdefault(token, interest)
    return mapping


def profile_overlap(passage: str, profile: ResearchProfile) -> float:
    needles: set[str] = set()
    for text in [*profile.interests, *profile.goals]:
        needles |= attention_module.tokenize(text)
    return _coverage(needles, attention_module.tokenize(passage))


def novelty(passage: str, profile: ResearchProfile) -> float:
    passage_tokens = attention_module.tokenize(passage)
    if not passage_tokens:
        return 0.0
    novel = passage_tokens - _known_tokens(profile)
    return attention_module.clamp01(len(novel) / len(passage_tokens))


def unresolved_overlap(passage: str, profile: ResearchProfile) -> float:
    passage_tokens = attention_module.tokenize(passage)
    scores = [
        _coverage(attention_module.tokenize(interest), passage_tokens)
        for interest in profile.unresolved_interests
        if attention_module.tokenize(interest)
    ]
    return max(scores) if scores else 0.0


def bridge_component(
    passage: str,
    profile: ResearchProfile,
    *,
    bridges: Mapping[str, Sequence[str]] | None = None,
) -> tuple[float, str | None, list[str]]:
    """Return (B, trigger, novel bridge terms) using the live DOMAIN_BRIDGES table.

    B is 1 only when a profile-interest token occurs in the passage and a bridge
    term from an entry whose trigger is itself a profile-interest token also
    occurs, and that bridge term is not already in a known claim.
    """
    table = attention_module.DOMAIN_BRIDGES if bridges is None else bridges
    passage_tokens = attention_module.tokenize(passage)
    interest_tokens = _interest_token_map(profile)
    if not (passage_tokens & set(interest_tokens)):
        return 0.0, None, []
    known = _known_tokens(profile)
    for trigger, terms in table.items():
        if trigger not in interest_tokens:
            continue
        hits = sorted(term for term in terms if term in passage_tokens and term not in known)
        if hits:
            return 1.0, trigger, hits
    return 0.0, None, []


def contradiction_component(passage: str, profile: ResearchProfile) -> float:
    """1 only when the same subject and predicate appear with a different object."""
    haystack = passage.lower()
    for claim in profile.known_claims:
        if claim.subject.lower() not in haystack:
            continue
        cue = _PREDICATE_CUES.get(claim.predicate, claim.predicate.replace("_", " "))
        match = re.search(rf"\b{re.escape(cue)}\s+([^.;\n]+)", passage, flags=re.IGNORECASE)
        if match is None:
            continue
        found = " ".join(match.group(1).strip(" \"'").split()).lower()
        known = " ".join(claim.object.split()).lower()
        if not found or known == found or known in found or found in known:
            continue
        return 1.0
    return 0.0


def occurring_interests(passage: str, profile: ResearchProfile) -> list[str]:
    passage_tokens = attention_module.tokenize(passage)
    found: list[str] = []
    for interest in profile.unresolved_interests:
        if interest in profile.interests and attention_module.tokenize(interest) & passage_tokens:
            found.append(interest)
    for interest in profile.interests:
        if interest in found:
            continue
        if attention_module.tokenize(interest) & passage_tokens:
            found.append(interest)
    return found


def score_knowledge_value(
    passage: str,
    profile: ResearchProfile,
    *,
    bridges: Mapping[str, Sequence[str]] | None = None,
) -> KnowledgeValue:
    relevance = profile_overlap(passage, profile)
    novel = novelty(passage, profile)
    bridge, trigger, terms = bridge_component(passage, profile, bridges=bridges)
    interest = unresolved_overlap(passage, profile)
    conflict = contradiction_component(passage, profile)
    score = attention_module.clamp01(
        WEIGHT_R * relevance + WEIGHT_N * novel + WEIGHT_B * bridge + WEIGHT_I * interest + WEIGHT_C * conflict
    )
    return KnowledgeValue(
        R=relevance,
        N=novel,
        B=bridge,
        I=interest,
        C=conflict,
        score=score,
        bridge_trigger=trigger,
        bridge_terms=terms,
    )
