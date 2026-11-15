# Test results

Latest check: implementation commit `e8a1f68` (`Make the follow-up control prominent and harden LLM JSON parsing`).

Command, from `/Users/bradleyharaguchi/SearchHax-QA`, using `/Users/bradleyharaguchi/SearchHax/exploration/.venv`:

```text
python -m pytest exploration/tests qa/tests -m "not integration" -q --tb=short -p no:cacheprovider --override-ini=testpaths=
```

Result: 50 failed, 88 passed, 2 deselected, exit status 1. No Telem, Tavily, or LLM call was made. From `focus/`, `python -m unittest test_focus_attention.py test_answer_composer.py`: 24 passed. `test_api_create_keeps_the_research_profile` passes. The four new `extract_json_object` unit tests pass. Uncommitted trace and lantern files were not imported.

Failed:

- `qa/tests/test_focus_userinfo.py::test_url_userinfo_is_not_part_of_the_source_key`
- `qa/tests/test_excerpt_overlap.py::test_nonoverlapping_sentence_is_sent_to_the_model`
- `qa/tests/test_regex_short_circuit.py::test_later_sentence_is_not_hidden_by_the_investment_regex`
- `qa/tests/test_fetched_page_rank.py::test_fetched_page_is_what_the_controller_ranks`
- `qa/tests/test_fetch_lineage.py::test_fetch_interaction_is_recorded`
- `qa/tests/test_preamble_search.py::test_long_question_keeps_the_sentence_after_the_preamble`
- `qa/tests/test_cited_answer.py::test_blank_snippet_is_not_a_citation`
- `qa/tests/test_cited_answer.py::test_blank_model_text_is_not_a_successful_answer`
- `qa/tests/test_cited_answer.py::test_considered_source_is_labeled_in_the_answer`
- `qa/tests/test_search_rewrite.py::test_unrelated_nvidia_question_is_not_rewritten_to_coreweave`
- `qa/tests/test_empty_search_query.py::test_long_question_does_not_search_an_empty_query`
- `qa/tests/test_cited_answer.py::test_null_answer_body_is_a_blocked_answer`
- `qa/tests/test_cited_answer.py::test_source_title_cannot_add_another_source`
- `qa/tests/test_cited_answer.py::test_answer_does_not_publish_an_amount_missing_from_the_quote`
- `qa/tests/test_cited_answer.py::test_failed_answer_regeneration_keeps_the_stored_answer`
- `qa/tests/test_llm_preamble.py::test_preamble_example_is_not_stored_as_supported`
- `qa/tests/test_cited_answer.py::test_invented_marker_and_url_are_not_published`
- `qa/tests/test_cited_answer.py::test_answer_call_stops_when_the_llm_budget_is_spent`
- `qa/tests/test_blank_follow_up.py::test_blank_approved_query_is_not_searched`
- `qa/tests/test_focus_archive.py::test_archived_page_does_not_drop_the_open_follow_up`
- `qa/tests/test_blank_question.py::test_blank_question_is_rejected`
- `qa/tests/test_hypothesis_status.py::test_hypothesis_quote_is_not_a_supported_relationship`
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

1. Verified P0 requirements: 47 / 95 rows marked P0 in `qa/acceptance_matrix.md` are VERIFIED. `FOC-11`, `EXT-13`, `EXT-12`, `ATT-5`, `RET-18`, `RET-17`, `ANS-10`, `LOOP-11`, `ANS-9`, `ANS-8`, `RET-16`, `RET-15`, `ANS-7`, `ANS-6`, `ANS-5`, `ANS-4`, `EXT-11`, `ANS-1`, `ANS-2`, `LOOP-10`, `FOC-10`, `API-2`, `EXT-10`, `CTR-1`, `EXT-9`, `FOC-9`, `FOC-8`, `FOC-7`, `USG-1`, `EXT-8`, `FOC-6`, `FOC-5`, `FOC-4`, `FOC-3`, `CHK-4`, `RET-12`, `RET-11`, `RET-10`, `LOOP-9`, `GRF-9`, `EXT-7`, `EXT-6`, `GRF-8`, `RET-9`, `LOOP-7`, and `FOC-1` failed. `DEMO-3` was not rerun live. `UI-1` has no React graph. `API-1` passes: create stores the profile. `ANS-3` passes: a missing answer key stores an empty blocked answer.
2. Passing tests / executed tests: 88 / 138 offline pytest tests. 2 live tests deselected. Focus unit tests: 24 / 24.
3. Unimplemented: clickable React graph, Story B as a live web investigation, Story D, domain routing, continuous monitoring. The profile fixture covers the ceramic bridge offline. A Streamlit backend UI exists at `focus/ui_backend.py`.
4. Blocking failures: a URL username and secret stay in the canonical source key. A sentence with no question words is still omitted from the model excerpt. The other blockers on this commit still fail. See `qa/failure_report.md`.
5. Integration readiness: not ready. A source key can retain credentials from a URL.
6. Commit tested: `e8a1f68` (`Make the follow-up control prominent and harden LLM JSON parsing`).
7. Next validation priority: drop URL userinfo in `canonical_url`, and rerun `test_url_userinfo_is_not_part_of_the_source_key`.

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
