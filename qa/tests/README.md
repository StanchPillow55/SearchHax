# QA defect ledger

These tests come from `qa/exploration-verification`. Each one asserts the **correct** behaviour; a
failing test is an open, recorded defect, not a broken test. They are intentionally outside
`pytest.ini` testpaths, so CI stays green while the ledger stays visible.

```bash
python -m pytest qa/tests -q -p no:cacheprovider
```

## Current status (2026-11-20)

Commands were run with the pinned CI dependencies (pydantic 2.14.3, telem-sdk installed), no provider
keys and an empty `HOME`:

| Tree | Pass | Fail | Skip |
|---|---|---|---|
| `frontend/react-integration` (PR #4) | 54 | 39 | 0 |
| `frontend/qa-and-m7-followup` | 90 | 1 | 2 |

The often-quoted figure of 38 open defects comes from an interpreter without `telem-sdk`, where
`test_fetch_lineage` is skipped instead of failing. With telem-sdk installed, PR #4 shows 39 open
defects. The follow-up branch fixes 36 of them (commit "Fix QA-ledger defects…"). Each test below
states the expected behaviour, and a failing run reproduces the defect: run the test file named.

### Inventory

Fix and ownership: all fixed rows are in `frontend/qa-and-m7-followup` (stacked on PR #4), not PR #4.

| ID | Test (`qa/tests/…`) | Milestone | Severity | Status |
|---|---|---|---|---|
| Q01 | `test_blank_follow_up::test_blank_approved_query_is_not_searched` | M3 | P1 | fixed |
| Q02 | `test_blank_question::test_blank_question_is_rejected` | M3 | P1 | fixed |
| Q03 | `test_cited_answer::test_invented_marker_and_url_are_not_published` | M5 | P0 fabricated provenance | fixed |
| Q04 | `test_cited_answer::test_answer_does_not_publish_an_amount_missing_from_the_quote` | M5 | P0 fabricated evidence | fixed |
| Q05 | `test_cited_answer::test_source_title_cannot_add_another_source` | M5 | P0 fabricated provenance | fixed |
| Q06 | `test_cited_answer::test_considered_source_is_labeled_in_the_answer` | M5 | P1 | fixed |
| Q07 | `test_cited_answer::test_blank_model_text_is_not_a_successful_answer` | M5 | P1 | fixed |
| Q08 | `test_cited_answer::test_blank_snippet_is_not_a_citation` | M5 | P0 fabricated provenance | fixed |
| Q09 | `test_cited_answer::test_null_answer_body_is_a_blocked_answer` | M5 | P1 | fixed |
| Q10 | `test_cited_answer::test_answer_call_stops_when_the_llm_budget_is_spent` | M3/M10 | P0 uncontrolled provider calls | fixed |
| Q11 | `test_cited_answer::test_failed_answer_regeneration_keeps_the_stored_answer` | M5 | P0 lost state | fixed |
| Q12 | `test_contradicted_answer::test_contradicted_amount_is_not_labeled_supported` | M5 | P0 fabricated evidence | fixed |
| Q13 | `test_empty_search_query::test_long_question_does_not_search_an_empty_query` | M3 | P2 | **skipped: product decision** |
| Q14 | `test_excerpt_overlap::test_nonoverlapping_sentence_is_sent_to_the_model` | M3 | P1 | fixed |
| Q15 | `test_extraction_gaps::test_truncated_excerpt_note_is_not_a_follow_up_query` | M3 | P1 | fixed |
| Q16 | `test_fetch_lineage::test_fetch_interaction_is_recorded` | M4 | P1 | fixed (skips without telem-sdk) |
| Q17 | `test_focus_and_versions::test_focus_approves_the_story_c_independence_search` | M3 | P2 | **skipped: stale premise** |
| Q18 | `test_focus_and_versions::test_controller_stop_without_reason_code_still_stops` | M3 | P1 | fixed |
| Q19 | `test_focus_and_versions::test_string_false_stop_does_not_drop_the_approved_search` | M3 | P1 | fixed |
| Q20 | `test_focus_archive::test_archived_page_does_not_drop_the_open_follow_up` | M3 | P1 | fixed |
| Q21 | `test_hypothesis_status::test_hypothesis_quote_is_not_a_supported_relationship` | M5 | P0 fabricated evidence | fixed |
| Q22 | `test_idle_controller::test_no_action_and_no_stop_does_not_stay_running` | M3 | P1 | fixed |
| Q23 | `test_llm_preamble::test_preamble_example_is_not_stored_as_supported` | M5 | P0 fabricated evidence | fixed |
| Q24 | `test_preamble_search::test_long_question_keeps_the_sentence_after_the_preamble` | M3 | P1 | fixed |
| Q25 | `test_profile_value::test_recorded_profile_run_counts_every_stored_page` | M8/M10 | P1 | **open: needs a live re-recording** |
| Q26 | `test_provider_and_budget::test_provider_outage_is_recorded_and_the_investigation_stops` | M3 | P1 | fixed |
| Q27 | `test_provider_and_budget::test_web_path_does_not_accept_two_amounts_as_supported` | M5 | P0 fabricated evidence | fixed |
| Q28 | `test_provider_and_budget::test_negated_investment_sentence_is_not_supported` | M5 | P0 fabricated evidence | fixed |
| Q29 | `test_provider_and_budget::test_causal_demand_sentence_does_not_close_the_gap` | M3 | P1 | fixed |
| Q30 | `test_provider_and_budget::test_web_path_keeps_story_c_wire_as_one_origin_and_one_amount` | M5 | P0 fabricated provenance | fixed |
| Q31 | `test_provider_and_budget::test_failed_fetch_body_is_not_stored_as_evidence` | M5 | P0 fabricated evidence | fixed |
| Q32 | `test_provider_and_budget::test_failed_fetch_is_not_replayed_from_cache` | M5 | P0 fabricated evidence | fixed |
| Q33 | `test_provider_and_budget::test_empty_failed_fetch_is_recorded` | M3 | P1 | fixed |
| Q34 | `test_provider_and_budget::test_search_exception_is_recorded_instead_of_escaping` | M3 | P1 | fixed |
| Q35 | `test_provider_and_budget::test_fetch_exception_does_not_split_the_search_counter` | M3 | P1 | fixed |
| Q36 | `test_provider_and_budget::test_possessive_coreweave_is_not_an_investment_in_coreweave` | M5 | P0 fabricated evidence | fixed |
| Q37 | `test_regex_short_circuit::test_later_sentence_is_not_hidden_by_the_investment_regex` | M3 | P1 | fixed |
| Q38 | `test_relationship_id_collision::test_newline_in_a_name_does_not_drop_the_other_relationship` | M5 | P0 lost state | fixed |
| Q39 | `test_search_rewrite::test_unrelated_nvidia_question_is_not_rewritten_to_coreweave` | M3 | P1 | fixed |

### Open items in detail

- **Q25 — recorded live demo undercounts pages.** In `demo/integrated_profile_evaluation.json`
  (story_a), `urls_fetched + cache_hits = 5 + 0`, but 8 candidates are stored. *Expected:* every
  stored candidate is a counted fetch or cache hit. *Hypothesis:* the file was recorded before the
  fetch and cache counter fixes (Q33–Q35). *Fix:* re-record the live demo. That requires an
  authorized, billable run, and the file must not be edited by hand.
- **Q13 — empty search query.** The blank query itself is fixed: the planner never yields `''`,
  and the orchestrator refuses to send a blank query. The test also requires *no* search for a
  question whose text after a leading `.` is searchable; the planner now searches that sentence.
  *Needs a product decision:* should that text be searched?
- **Q17 — Story C independence search.** The premise is stale: `run_story_c()` already runs the
  independence follow-up and marks it executed, so there is no pending action to approve.
  *Needs a decision:* should Story C leave that action pending?

Fixed defects stay here as regression tests.
