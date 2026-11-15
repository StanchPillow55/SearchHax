# Test results

Latest check: implementation commit `6d87f2c` (`Record the bounded live profile-enabled integration run.`). The twenty-two QA failures from `31c389b` still fail. The recorded profile file adds one more reproduction of the cache-counter gap.

Command, from `/Users/bradleyharaguchi/SearchHax-QA`, using `/Users/bradleyharaguchi/SearchHax/exploration/.venv`:

```text
python -m pytest exploration/tests qa/tests -m "not integration" -q --tb=short -p no:cacheprovider --override-ini=testpaths=
```

Result: 28 failed, 80 passed, 2 deselected, exit status 1. No Telem, Tavily, or LLM call was made. From `focus/`, `python -m unittest test_focus_attention.py test_answer_composer.py`: 24 passed.

Failed:

- `qa/tests/test_api_profile.py::test_api_create_keeps_the_research_profile`
- `qa/tests/test_contract_schema.py::test_committed_schema_includes_profile_and_knowledge_value`
- `qa/tests/test_extraction_gaps.py::test_truncated_excerpt_note_is_not_a_follow_up_query`
- `qa/tests/test_profile_value.py::test_recorded_profile_run_counts_every_stored_page`
- `exploration/tests/test_integrated_pipeline.py::test_profile_live_pipeline_runs_a_follow_up_through_convergence`
- `exploration/tests/test_integrated_pipeline.py::test_profile_live_pipeline_stops_when_no_useful_action`
- `qa/tests/test_focus_parenthetical.py::test_quarter_number_is_not_a_source_citation`
- `qa/tests/test_focus_plan.py::test_investigate_follow_up_runs_inside_the_default_budget`
- `qa/tests/test_focus_url_citation.py::test_longer_url_is_not_cited_as_the_shorter_source`
- `qa/tests/test_cache_metrics.py::test_cached_fetch_increments_cache_hits`
- `qa/tests/test_provider_and_budget.py::test_possessive_coreweave_is_not_an_investment_in_coreweave`
- `qa/tests/test_focus_providers.py::test_one_provider_failure_keeps_the_other_providers_pages`
- `qa/tests/test_focus_answer.py::test_unknown_marker_is_not_shown_with_a_valid_citation`
- `qa/tests/test_focus_loop.py::test_identical_follow_up_is_issued_once`
- `qa/tests/test_focus_fetch.py::test_failed_fetch_body_is_not_used_as_page_text`
- `qa/tests/test_provider_and_budget.py::test_fetch_exception_does_not_split_the_search_counter`
- `qa/tests/test_provider_and_budget.py::test_search_exception_is_recorded_instead_of_escaping`
- `qa/tests/test_provider_and_budget.py::test_empty_failed_fetch_is_recorded`
- `qa/tests/test_provider_and_budget.py::test_failed_fetch_is_not_replayed_from_cache`
- `qa/tests/test_provider_and_budget.py::test_failed_fetch_body_is_not_stored_as_evidence`
- `qa/tests/test_focus_and_versions.py::test_string_false_stop_does_not_drop_the_approved_search`
- `qa/tests/test_provider_and_budget.py::test_web_path_keeps_story_c_wire_as_one_origin_and_one_amount`
- `qa/tests/test_provider_and_budget.py::test_causal_demand_sentence_does_not_close_the_gap`
- `qa/tests/test_provider_and_budget.py::test_negated_investment_sentence_is_not_supported`
- `qa/tests/test_provider_and_budget.py::test_web_path_does_not_accept_two_amounts_as_supported`
- `qa/tests/test_provider_and_budget.py::test_provider_outage_is_recorded_and_the_investigation_stops`
- `qa/tests/test_focus_and_versions.py::test_controller_stop_without_reason_code_still_stops`
- `qa/tests/test_focus_and_versions.py::test_focus_approves_the_story_c_independence_search`

A read-only check of the gitignored file `exploration/data/cold/story.sqlite` on the implementation machine, investigation `inv_8e46a18764e64eb0`, found 0 span offset mismatches across 3 spans and 6 links. The 6 supported rows are 2 facts on 3 pages. `llm_tokens` and `cost_usd` are null. That file is not in the commit.

1. Verified P0 requirements: 43 / 69 rows marked P0 in `qa/acceptance_matrix.md` are VERIFIED. `API-1`, `CTR-1`, `EXT-9`, `FOC-9`, `FOC-8`, `FOC-7`, `USG-1`, `EXT-8`, `FOC-6`, `FOC-5`, `FOC-4`, `FOC-3`, `CHK-4`, `RET-12`, `RET-11`, `RET-10`, `LOOP-9`, `GRF-9`, `EXT-7`, `EXT-6`, `GRF-8`, `RET-9`, `LOOP-7`, and `FOC-1` failed. `DEMO-3` was not rerun live. `UI-1` has no React graph. `DEMO-4` passes: the recorded Story C B0 and B3 counts match a fresh offline run.
2. Passing tests / executed tests: 80 / 108 offline pytest tests. 2 live tests deselected. Focus unit tests: 24 / 24.
3. Unimplemented: clickable React graph, Story B as a live web investigation, Story D, domain routing, continuous monitoring. The profile fixture covers the ceramic bridge offline.
4. Blocking failures: `POST /api/exploration/investigations` accepts a profile and returns 200, then the export's `profile` is null. The committed evidence schema also omits the profile and the knowledge-value score. The other blockers on this commit still fail. See `qa/failure_report.md`.
5. Integration readiness: not ready. The HTTP API cannot start the profile investigation that the orchestrator can.
6. Commit tested: `6d87f2c` (`Record the bounded live profile-enabled integration run.`).
7. Next validation priority: accept `profile` on create and return it on the export. Rerun `test_api_create_keeps_the_research_profile`. Then regenerate `shared/evidence.schema.json`.

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
