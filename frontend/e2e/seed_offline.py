"""Seed a fresh SQLite database for the browser tests, offline (fixture corpora only).

Usage: python frontend/e2e/seed_offline.py <db_path> <env_file>

Writes E2E_* variables to <env_file> naming the seeded records. No provider is called:
Story C and the profile run read local fixtures, the convergence controller is replaced by
the labelled fallback, and branches are saved without research. The one "legacy" row
reproduces the pre-1.1.0 shape exactly as exploration/tests/test_branch_context_regression.py
does, so the legacy-branch view can be tested without a historical database.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "focus")]

from exploration.backend.orchestrator import Orchestrator  # noqa: E402
from exploration.backend.trace import create_branch  # noqa: E402
from shared.contracts import CreateBranchRequest  # noqa: E402


def _offline(*_args, **_kwargs):
    raise ConnectionError("offline seed: labelled fallback convergence")


def main(db_path: str, env_file: str) -> None:
    db = Path(db_path)
    if db.exists():
        raise SystemExit(f"refusing to seed an existing database: {db}")
    orchestrator = Orchestrator(db, post=_offline)
    profiled = orchestrator.run_profile()
    story = orchestrator.run_story_c()
    root_id = story.investigation.id
    checkpoint = story.checkpoints[-1]
    snapshot_claims = set((checkpoint.state_json.get("snapshot") or {}).get("claim_ids") or [])
    supported = [c for c in story.claims if c.status == "supported" and (not snapshot_claims or c.id in snapshot_claims)]
    claim = supported[0]

    child = create_branch(
        orchestrator,
        root_id,
        CreateBranchRequest(
            from_checkpoint_id=checkpoint.id,
            objective=f"Find independent evidence for or against: {claim.text}",
            intervention_type="challenge_evidence",
            attached_claim_ids=[claim.id],
            constraints={"max_searches": 1},
        ),
    )

    legacy = create_branch(
        orchestrator,
        root_id,
        CreateBranchRequest(from_checkpoint_id=story.checkpoints[0].id, objective="Look at energy costs", intervention_type="fork"),
    )
    legacy_id = legacy.child_investigation_id
    export = orchestrator.get(legacy_id)
    metadata = dict(export.investigation.metadata)
    for key in ("root_question", "parent_question", "lifecycle", "objective_grounded"):
        metadata.pop(key, None)
    metadata["objective"] = "Is this true?"
    metadata["intervention_type"] = "challenge_evidence"
    with orchestrator.database._lock:
        orchestrator.database._conn.execute(
            "UPDATE investigations SET question = ?, status = 'running', metadata_json = ? WHERE id = ?",
            ("Is this true?", json.dumps(metadata), legacy_id),
        )
        orchestrator.database._conn.commit()
    orchestrator.database.close()

    values = {
        "E2E_INVESTIGATION": root_id,
        "E2E_OTHER_INVESTIGATION": profiled.investigation.id,
        "E2E_CLAIM": claim.id,
        "E2E_CHILD_WITH_RESEARCH": child.child_investigation_id,
        "E2E_LEGACY_BRANCH": legacy_id,
    }
    Path(env_file).write_text("".join(f"{k}={v}\n" for k, v in values.items()), encoding="utf-8")
    print(json.dumps(values))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
