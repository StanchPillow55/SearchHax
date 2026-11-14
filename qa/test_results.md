# Test results

Latest check: implementation commit `8e3e6e5` on QA branch `qa/exploration-verification`.

Command, from `/Users/bradleyharaguchi/SearchHax-QA`, using `/Users/bradleyharaguchi/SearchHax/exploration/.venv`:

```text
python -m pytest exploration/tests qa/tests -m "not integration" -q --tb=short -p no:cacheprovider --override-ini=testpaths=
```

Result: 6 failed, 59 passed, 2 deselected, exit status 1. No Telem, Tavily, or LLM call was made.

Failed:

- `qa/tests/test_provider_and_budget.py::test_causal_demand_sentence_does_not_close_the_gap`
- `qa/tests/test_provider_and_budget.py::test_negated_investment_sentence_is_not_supported`
- `qa/tests/test_provider_and_budget.py::test_web_path_does_not_accept_two_amounts_as_supported`
- `qa/tests/test_provider_and_budget.py::test_provider_outage_is_recorded_and_the_investigation_stops`
- `qa/tests/test_focus_and_versions.py::test_controller_stop_without_reason_code_still_stops`
- `qa/tests/test_focus_and_versions.py::test_focus_approves_the_story_c_independence_search`

A read-only check of the gitignored file `exploration/data/cold/story.sqlite` on the implementation machine, investigation `inv_8e46a18764e64eb0`, found 0 span offset mismatches across 3 spans and 6 links. The 6 supported rows are 2 facts on 3 pages. `llm_tokens` and `cost_usd` are null. That file is not in the commit.

1. Verified P0 requirements: 36 / 44 rows marked P0 in `qa/acceptance_matrix.md` are VERIFIED. `EXT-7`, `EXT-6`, `GRF-8`, `RET-9`, `LOOP-7`, and `FOC-1` failed. `DEMO-3` was not rerun live. `UI-1` has no React graph.
2. Passing tests / executed tests: 59 / 65 offline pytest tests. 2 live tests deselected.
3. Unimplemented: clickable React graph, Story B, Story D, domain routing, continuous monitoring.
4. Blocking failures: a causal demand sentence closes the gap; a negated investment sentence becomes supported; the web loop keeps two disagreeing amounts `supported`; a provider outage stays `running`; a reason-less controller stop stays `running`; the focus handoff cancels the Story C independence search. See `qa/failure_report.md`.
5. Integration readiness: not ready. Story C conflict detection, affirmative quote offsets, checkpoint reload, and the two-search cap pass. Demand-gap handling and the web conflict check do not.
6. Commit tested: `8e3e6e5` (`Merge origin/main into feat/exploration.`).
7. Next validation priority: keep the demand question open when the only mention is a causal sentence, then stop treating a negated investment clause as support. Rerun the six failing tests.

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
