# Test results

Latest check: implementation commit `8e3e6e5`. QA merge `6dab401` on `qa/exploration-verification`.

```text
53 passed, 2 deselected, exit status 0
focus/test_focus_attention.py: 5 passed
```

1. Verified P0 requirements: the offline P0 checks that failed on `edf9e32` pass on `8e3e6e5`. Live Telem was not repeated. A live Convergence server was not part of this run.
2. Passing tests / executed tests: 53 / 53 offline pytest tests, plus 5 focus unit tests. 2 live tests deselected.
3. Unimplemented: clickable React graph, Story B, Story D, domain routing, continuous monitoring.
4. Blocking failures: none on `8e3e6e5`.
5. Integration readiness: offline Story C, focus handoff, and stored Story A replay pass. This run did not call a live Convergence process.
6. Commit tested: `8e3e6e5` (`Merge origin/main into feat/exploration.`).
7. Next validation priority: one budgeted live Telem smoke only if the owner authorizes another credit spend.

Previous release check: implementation commit `c81ea8e`, QA commit that imports it is recorded in `qa/release_report.md`.

Previous snapshot `edf9e32` remains below.

Implementation commit: `edf9e323d3ce7810b81c4f88d99bba48700e07dc` (`edf9e32` on `feat/exploration`).

QA worktree: `/Users/bradleyharaguchi/SearchHax-QA` branch `qa/exploration-verification` at that same commit, plus these QA files.

Command:

```text
/Users/bradleyharaguchi/SearchHax/exploration/.venv/bin/python -m pytest qa/tests -q --tb=line -p no:cacheprovider --override-ini=testpaths=qa/tests
```

Exit status: 1.

```text
4 failed, 13 passed, 2 warnings in 3.65s
FAILED qa/tests/test_evidence_and_loop.py::test_repeated_entity_on_follow_up_does_not_crash
FAILED qa/tests/test_evidence_and_loop.py::test_duplicate_controller_query_is_not_executed
FAILED qa/tests/test_evidence_and_loop.py::test_unresolved_gap_changes_which_page_is_fetched
FAILED qa/tests/test_evidence_and_loop.py::test_committed_story_a_record_is_internally_consistent
```

No live provider call was issued. `exploration/tests/test_telem_live.py` and `exploration/tests/test_telem_integration.py` were not run.

## Milestone

1. Verified P0 requirements: 8 / 12
2. Passing tests / executed tests: 13 / 17
3. Unimplemented: clickable React graph, Story B, Story D, walkthrough recording, domain routing, continuous monitoring
4. Blocking failures: follow-up entity crash, duplicate controller query, stale Story A demo record
5. Integration readiness: not ready. Story C and the fallback controller path pass. A second web step that repeats an entity crashes, and the committed Story A record has no grounded relationships.
6. Commit tested: `edf9e323d3ce7810b81c4f88d99bba48700e07dc`
7. Next validation priority: after the entity upsert and duplicate-query guard land, re-test the web follow-up and regenerate `demo/evaluation.json` without a live credit loop unless one budgeted smoke call is explicitly authorized.
