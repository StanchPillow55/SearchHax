# Test results

Latest check: implementation commit `8e3e6e5` on QA branch `qa/exploration-verification`.

Command, from `/Users/bradleyharaguchi/SearchHax-QA`, using `/Users/bradleyharaguchi/SearchHax/exploration/.venv`:

```text
python -m pytest exploration/tests qa/tests -m "not integration" -q --tb=short -p no:cacheprovider --override-ini=testpaths=
```

Result: 1 failed, 58 passed, 2 deselected, exit status 1. No Telem, Tavily, or LLM call was made.

Failed: `qa/tests/test_focus_and_versions.py::test_focus_approves_the_story_c_independence_search`.

1. Verified P0 requirements: 35 / 38 rows marked P0 in `qa/acceptance_matrix.md` are VERIFIED. `FOC-1` failed. `DEMO-3` was not rerun live. `UI-1` has no React graph.
2. Passing tests / executed tests: 58 / 59 offline pytest tests. 2 live tests deselected.
3. Unimplemented: clickable React graph, Story B, Story D, domain routing, continuous monitoring.
4. Blocking failures: the focus handoff stops Story C at `low_expected_value` and does not approve the utility-0.9 independence search. See `qa/failure_report.md`.
5. Integration readiness: not ready for the focus controller. The fallback Story C path, quote checks, checkpoint reload, and the stored Story A replay pass. A live Convergence process was not called.
6. Commit tested: `8e3e6e5` (`Merge origin/main into feat/exploration.`).
7. Next validation priority: fix `evaluate_with_focus` so an archived shared-origin set does not cancel a high-utility follow-up, then rerun `test_focus_approves_the_story_c_independence_search`.

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
