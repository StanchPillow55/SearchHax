# Test results

Latest check: implementation commit `8e3e6e5` on QA branch `qa/exploration-verification`.

Command, from `/Users/bradleyharaguchi/SearchHax-QA`, using `/Users/bradleyharaguchi/SearchHax/exploration/.venv`:

```text
python -m pytest exploration/tests qa/tests -m "not integration" -q --tb=short -p no:cacheprovider --override-ini=testpaths=
```

Result: 3 failed, 59 passed, 2 deselected, exit status 1. No Telem, Tavily, or LLM call was made.

Failed:

- `qa/tests/test_focus_and_versions.py::test_focus_approves_the_story_c_independence_search`
- `qa/tests/test_focus_and_versions.py::test_controller_stop_without_reason_code_still_stops`
- `qa/tests/test_provider_and_budget.py::test_provider_outage_is_recorded_and_the_investigation_stops`

A read-only check of the gitignored file `exploration/data/cold/story.sqlite` on the implementation machine, investigation `inv_8e46a18764e64eb0`, found 0 span offset mismatches across 3 spans and 6 links. The 6 supported rows are 2 facts on 3 pages. `llm_tokens` and `cost_usd` are null. That file is not in the commit.

1. Verified P0 requirements: 36 / 41 rows marked P0 in `qa/acceptance_matrix.md` are VERIFIED. `FOC-1`, `LOOP-7`, and `RET-9` failed. `DEMO-3` was not rerun live. `UI-1` has no React graph.
2. Passing tests / executed tests: 59 / 62 offline pytest tests. 2 live tests deselected.
3. Unimplemented: clickable React graph, Story B, Story D, domain routing, continuous monitoring.
4. Blocking failures: a provider outage stays `running` with no recorded error; a controller `stop: true` without a reason code stays `running`; the focus handoff cancels the Story C independence search. See `qa/failure_report.md`.
5. Integration readiness: not ready. Quote checks, checkpoint reload, the two-search cap, and the stored Story A quotes pass. Provider failure, a reason-less stop, and the focus decision do not.
6. Commit tested: `8e3e6e5` (`Merge origin/main into feat/exploration.`).
7. Next validation priority: record a total provider outage as a stop, apply a reason-less controller stop, and approve the Story C independence action when the current pages are archived. Rerun the three failing tests.

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
