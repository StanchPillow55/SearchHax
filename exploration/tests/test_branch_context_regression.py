"""Regression tests for the branch context-loss defect ("Is this true?").

Observed in persisted records (exploration.sqlite, 2026-11-15):

  parent  inv_93606fb27bb74f3c  "How do NVIDIA's investments, ... reinforce one another?"
  child   inv_c07010e29b434741  fork, objective "Is this true?"   -> question became "Is this true?"
  grand   inv_390477badbf24e65  challenge_evidence, objective ""  -> searched the literal "Is this true?"

Fixed in contract 1.1.0 (Milestone 2):
  * a branch keeps the ROOT research question; the objective is stored separately;
  * a challenge needs an attached claim or a grounded objective (422 otherwise);
  * a vague objective is resolved against the attached claim before retrieval;
  * saved (not started) is a lifecycle state distinct from researching;
  * legacy rows that overwrote the question are resolved by walking parent links, and a
    legacy ungrounded challenge stops without searching.

Offline: FakeRetrieval, convergence stubbed down. No provider calls.
"""

import json

import pytest

from exploration.backend.orchestrator import Orchestrator
from exploration.backend.planner import branch_query, is_grounded_objective
from exploration.backend.trace import build_trace, create_branch, lifecycle_of, resolve_root_question, resume_branch
from exploration.tests.test_lantern_trace import FakeRetrieval, _down
from shared.contracts import BranchRecord, CreateBranchRequest

VAGUE = "Is this true?"


def _setup(tmp_path):
    orchestrator = Orchestrator(tmp_path / "branch-context.sqlite")
    orchestrator.post = _down
    fake = FakeRetrieval()
    orchestrator.retrieval = fake
    parent = orchestrator.run_story_c()
    claim = next(c for c in parent.checkpoints[0].state_json["snapshot"]["claims"] if c.get("text"))
    return orchestrator, fake, parent, claim


def _branch(orchestrator, parent_id, checkpoint_id, **kwargs):
    return create_branch(
        orchestrator,
        parent_id,
        CreateBranchRequest(from_checkpoint_id=checkpoint_id, constraints={"max_searches": 1}, **kwargs),
    )


# --------------------------------------------------------------------------- grounding helpers


@pytest.mark.parametrize("text", ["", "   ", VAGUE, "is it true", "verify this", "Check that claim.", "Really?", "Challenge the amount"])
def test_vague_objectives_are_not_grounded(text):
    assert not is_grounded_objective(text)


@pytest.mark.parametrize("text", ["Look at energy costs", "NVIDIA CoreWeave $2 billion stake", "Investigate whether energy costs undermine the conclusion"])
def test_specific_objectives_are_grounded(text):
    assert is_grounded_objective(text)


def test_branch_query_never_returns_a_vague_prompt():
    for kind in ("fork", "challenge_evidence"):
        query, planned = branch_query(root_question="Root?", objective=VAGUE, attached_claims=[], intervention_type=kind)
        assert query is None
        assert planned["objective_grounded"] is False


# --------------------------------------------------------------------------- the original defect, fixed


def test_fork_keeps_the_root_question_and_stores_the_objective_separately(tmp_path):
    orchestrator, _fake, parent, claim = _setup(tmp_path)
    cases = [("fork", {}), ("challenge_evidence", {"attached_claim_ids": [claim["id"]]})]
    for kind, extra in cases:
        branch = _branch(orchestrator, parent.investigation.id, parent.checkpoints[0].id, objective=VAGUE, intervention_type=kind, **extra)
        child = orchestrator.get(branch.child_investigation_id)
        assert child.investigation.question == parent.investigation.question
        assert child.investigation.metadata["root_question"] == parent.investigation.question
        assert child.investigation.metadata["objective"] == VAGUE
        trace = build_trace(orchestrator.database, child.investigation.id)
        assert trace.question == parent.investigation.question
        assert trace.branch_objective == VAGUE


def test_grandchild_inherits_the_root_question(tmp_path):
    orchestrator, _fake, parent, _claim = _setup(tmp_path)
    fork = _branch(orchestrator, parent.investigation.id, parent.checkpoints[0].id, objective=VAGUE, intervention_type="fork")
    child = orchestrator.get(fork.child_investigation_id)
    grand = _branch(orchestrator, child.investigation.id, child.checkpoints[0].id, objective="", intervention_type="fork")
    grand_export = orchestrator.get(grand.child_investigation_id)
    assert grand_export.investigation.question == parent.investigation.question
    assert grand_export.investigation.metadata["parent_question"] == parent.investigation.question


def test_vague_challenge_query_is_grounded_in_the_attached_claim(tmp_path):
    orchestrator, fake, parent, claim = _setup(tmp_path)
    challenge = _branch(
        orchestrator,
        parent.investigation.id,
        parent.checkpoints[0].id,
        objective=VAGUE,
        intervention_type="challenge_evidence",
        attached_claim_ids=[claim["id"]],
    )
    resume_branch(orchestrator, challenge.id)
    assert len(fake.queries) == 1
    query = fake.queries[0].lower()
    assert query != VAGUE.lower()
    claim_words = {w for w in claim["text"].lower().split() if len(w) > 3}
    assert len(claim_words & set(query.split())) >= min(3, len(claim_words))
    search = next(e for e in orchestrator.database.list_events(challenge.child_investigation_id) if e.stage == "search")
    assert search.payload["planned_from"]["claim_ids"] == [claim["id"]]
    assert search.payload["planned_from"]["objective_grounded"] is False


def test_ungrounded_challenge_is_refused_without_searching(tmp_path):
    orchestrator, fake, parent, _claim = _setup(tmp_path)
    before = orchestrator.database.list_investigations(200)[1]
    for objective in ("", "   ", VAGUE):
        with pytest.raises(ValueError, match="not specific enough"):
            _branch(orchestrator, parent.investigation.id, parent.checkpoints[0].id, objective=objective, intervention_type="challenge_evidence")
    assert fake.queries == []
    assert orchestrator.database.list_investigations(200)[1] == before


def test_vague_fork_does_not_search_the_vague_text(tmp_path):
    orchestrator, fake, parent, _claim = _setup(tmp_path)
    fork = _branch(orchestrator, parent.investigation.id, parent.checkpoints[0].id, objective=VAGUE, intervention_type="fork")
    child = orchestrator.get(fork.child_investigation_id)
    assert all(q.kind != "branch_objective" for q in child.unresolved_questions)
    resume_branch(orchestrator, fork.id)
    assert VAGUE.lower() not in [q.lower() for q in fake.queries]


# --------------------------------------------------------------------------- lifecycle


def test_saved_child_is_not_reported_as_running(tmp_path):
    orchestrator, fake, parent, _claim = _setup(tmp_path)
    fork = _branch(orchestrator, parent.investigation.id, parent.checkpoints[0].id, objective="Look at energy costs", intervention_type="fork")
    child = orchestrator.get(fork.child_investigation_id)
    assert fake.queries == []
    assert child.investigation.status == "created"
    assert child.investigation.metadata["lifecycle"] == "saved"
    assert lifecycle_of(child.investigation) == "saved"
    # The grounded objective steers the first follow-up.
    focus = [q for q in child.unresolved_questions if q.kind == "branch_objective"]
    assert [q.text for q in focus] == ["Look at energy costs"]


def test_running_a_saved_child_moves_it_out_of_saved(tmp_path):
    orchestrator, fake, parent, claim = _setup(tmp_path)
    challenge = _branch(orchestrator, parent.investigation.id, parent.checkpoints[0].id, objective="", intervention_type="challenge_evidence", attached_claim_ids=[claim["id"]])
    result = resume_branch(orchestrator, challenge.id)
    assert len(fake.queries) == 1
    assert result.investigation.usage.search_calls == 1
    stored = orchestrator.get(challenge.child_investigation_id).investigation
    assert stored.metadata["lifecycle"] in {"researching", "stopped", "completed"}
    assert stored.metadata["lifecycle"] == lifecycle_of(stored)


def test_a_failing_step_is_recorded_as_failed_without_results(tmp_path):
    orchestrator, _fake, parent, claim = _setup(tmp_path)
    challenge = _branch(orchestrator, parent.investigation.id, parent.checkpoints[0].id, objective="", intervention_type="challenge_evidence", attached_claim_ids=[claim["id"]])

    class Broken:
        dry_run = True

        def search(self, *_a, **_k):
            raise RuntimeError("provider exploded")

    orchestrator.retrieval = Broken()
    with pytest.raises(RuntimeError):
        resume_branch(orchestrator, challenge.id)
    stored = orchestrator.get(challenge.child_investigation_id).investigation
    assert stored.metadata["lifecycle"] == "failed"
    assert "provider exploded" in stored.metadata["last_error"]
    assert stored.usage.search_calls == 0


# --------------------------------------------------------------------------- legacy rows


def _legacy_overwritten_child(orchestrator, parent, objective, kind):
    """Recreate a pre-1.1.0 row: question overwritten, no root_question, status running."""
    branch = _branch(orchestrator, parent.investigation.id, parent.checkpoints[0].id, objective="Look at energy costs", intervention_type="fork")
    child_id = branch.child_investigation_id
    export = orchestrator.get(child_id)
    metadata = dict(export.investigation.metadata)
    for key in ("root_question", "parent_question", "lifecycle", "objective_grounded"):
        metadata.pop(key, None)
    metadata["objective"] = objective
    metadata["intervention_type"] = kind
    # The question is immutable through the normal write path, so write the legacy shape
    # directly, exactly as pre-1.1.0 create_branch stored it.
    db = orchestrator.database
    with db._lock:
        db._conn.execute(
            "UPDATE investigations SET question = ?, status = 'running', metadata_json = ? WHERE id = ?",
            (objective or parent.investigation.question, json.dumps(metadata), child_id),
        )
        db._conn.commit()
    return branch, orchestrator.get(child_id)


def test_legacy_overwritten_branch_resolves_the_root_question_by_lineage(tmp_path):
    orchestrator, _fake, parent, _claim = _setup(tmp_path)
    _branch_rec, legacy = _legacy_overwritten_child(orchestrator, parent, VAGUE, "fork")
    assert legacy.investigation.question == VAGUE
    assert resolve_root_question(orchestrator, legacy) == parent.investigation.question
    assert lifecycle_of(legacy.investigation) == "saved"  # running with zero searches
    trace = build_trace(orchestrator.database, legacy.investigation.id)
    assert trace.root_question == parent.investigation.question
    assert trace.lifecycle == "saved"
    row = next(item for item in orchestrator.database.list_investigations(200)[0] if item["id"] == legacy.investigation.id)
    assert row["question"] == VAGUE
    assert row["root_question"] == parent.investigation.question
    assert row["lifecycle"] == "saved"
    # A new branch from the legacy row gets the true root question.
    grand = _branch(orchestrator, legacy.investigation.id, legacy.checkpoints[0].id, objective="", intervention_type="fork")
    assert orchestrator.get(grand.child_investigation_id).investigation.question == parent.investigation.question


def test_legacy_ungrounded_challenge_stops_without_searching(tmp_path):
    """The exact inv_390477badbf24e65 shape: challenge, empty objective, no claims."""
    orchestrator, fake, parent, _claim = _setup(tmp_path)
    branch, legacy = _legacy_overwritten_child(orchestrator, parent, "", "challenge_evidence")
    legacy_branch = BranchRecord.model_validate(
        {**branch.model_dump(mode="json"), "intervention_type": "challenge_evidence", "objective": ""}
    )
    assert legacy_branch.child_investigation_id == legacy.investigation.id
    result = orchestrator.step(legacy.investigation.id)
    assert fake.queries == []
    assert result.investigation.status == "stopped"
    assert result.investigation.stop_reason == "no_useful_actions"
    assert result.investigation.usage.search_calls == 0


# --------------------------------------------------------------------------- invariant


def test_branching_and_resuming_leave_the_parent_byte_identical(tmp_path):
    orchestrator, _fake, parent, claim = _setup(tmp_path)
    pid = parent.investigation.id
    before_export = orchestrator.get(pid).model_dump(mode="json")
    before_trace = build_trace(orchestrator.database, pid).model_dump(mode="json")
    challenge = _branch(orchestrator, pid, parent.checkpoints[0].id, objective=VAGUE, intervention_type="challenge_evidence", attached_claim_ids=[claim["id"]])
    resume_branch(orchestrator, challenge.id)
    assert orchestrator.get(pid).model_dump(mode="json") == before_export
    assert build_trace(orchestrator.database, pid).model_dump(mode="json") == before_trace


def test_every_new_search_records_its_round_and_what_prompted_it(tmp_path):
    orchestrator, fake, parent, claim = _setup(tmp_path)
    challenge = _branch(orchestrator, parent.investigation.id, parent.checkpoints[0].id, objective="", intervention_type="challenge_evidence", attached_claim_ids=[claim["id"]])
    resume_branch(orchestrator, challenge.id)
    searches = [e for e in orchestrator.database.list_events(challenge.child_investigation_id) if e.stage == "search"]
    assert searches
    assert [e.payload["round"] for e in searches] == list(range(1, len(searches) + 1))
    assert all("planned_from" in e.payload for e in searches)
