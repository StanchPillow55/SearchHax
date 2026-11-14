# Acceptance matrix

Earlier snapshot: `edf9e32`. Release check: `c81ea8e`, see `qa/release_report.md`.

Statuses are from the QA tests in `qa/tests/` and from `demo/evaluation.json` in that commit. Developer tests were not treated as proof.

| ID | Description | Priority | Expected behavior | Code | Test | Status | Evidence |
| --- | --- | --- | --- | --- | --- | --- | --- |
| RET-1 | Canonical URL normalization | P0 | Fragment, host case, and trailing slash collapse to one URL | `exploration/backend/retrieval.py` `normalize_url` | `test_url_normalization_collapses_fragment_host_and_trailing_slash` | VERIFIED | Passed |
| RET-2 | Provider metadata retained | P0 | Each provider hit stays on the merged document | `retrieval.py` `merge_provider_hits` | `test_duplicate_provider_hits_keep_metadata_and_count_as_one_source` | VERIFIED | Passed |
| RET-3 | Same URL is one source | P0 | Brave and Tavily hits for one URL count as one source | `retrieval.py` `independent_source_count` | same test | VERIFIED | Passed |
| RET-4 | Network and rate-limit errors | P0 | 400 is not retried; 429 stops after two retries | `retrieval.py` `call_with_retries` | `test_non_transient_errors_are_not_retried_and_rate_limits_stop` | VERIFIED | Passed. 429 ran 3 times, 400 ran once |
| RET-5 | Session lineage | P0 | Later searches reuse `session_id` and keep interaction ids | `retrieval.py` `RetrievalClient.search` | `test_session_lineage_is_reused_and_search_budget_is_enforced` | VERIFIED | Passed |
| RET-6 | Search and fetch budgets | P0 | Third search and a 6-URL fetch are refused | `budget.py`, `retrieval.py` | session test and `test_fetch_batch_cap_and_cache_reuse` | VERIFIED | Passed |
| RET-7 | Fetch cache reuse | P0 | A second fetch of the same URL does not call the provider | `retrieval.py` `fetch` | `test_fetch_batch_cap_and_cache_reuse` | VERIFIED | Passed. One provider call |
| ATT-1 | Score range and formula | P0 | `0.4R+0.3G+0.2D+0.1F` stays in 0–1 | `attention.py` `score_passage` | `test_attention_formula_bounds_and_gap_effect` | VERIFIED | Passed |
| ATT-2 | Gaps change the score | P0 | Passing a gap raises G and the score | `attention.py` | same test | VERIFIED | Passed for the function |
| ATT-3 | Gaps change fetch choice | P0 | The open gap decides which snippet is fetched when one slot remains | `orchestrator.py` line 426 | `test_unresolved_gap_changes_which_page_is_fetched` | FAILED | Fetch selected the query-only URL. See failure report |
| ATT-4 | Attention is not confidence | P0 | The score field is documented as not factual confidence, and a bad quote is not supported | `attention.py`, `extraction.py` | attention test and `test_quotes_must_exist_and_bad_quotes_cannot_support_edges` | VERIFIED | Passed |
| EXT-1 | Stable claim ids | P0 | The same document and quote produce the same claim id | `extraction.py` | quote test | VERIFIED | Passed |
| EXT-2 | Exact quotations and offsets | P0 | Span text equals the stored slice | `verification.py` `assess_quotation` | quote test and Story C helper | VERIFIED | Passed |
| EXT-3 | Invalid quotations | P0 | A quote absent from the page cannot be a supported edge | `extraction.py` `_add_grounded` | quote test | VERIFIED | `caused` stayed unsupported |
| EXT-4 | Extraction failure | P0 | A structured-output exception returns a blocked batch | `extraction.py` `_extract_with_llm` | `test_extraction_failure_does_not_crash_or_invent_relationships` | VERIFIED | Passed |
| EXT-5 | Repeated entity on a later page | P0 | The investigation save survives a second document with the same entity | `database.py` lines 341–345 | `test_repeated_entity_on_follow_up_does_not_crash` | VERIFIED | Passed on `c81ea8e` |
| GRF-1 | Evidence links and quotes | P0 | Supported and contradicted edges point at a real span | Story C graph | `test_story_c_provenance_contradiction_and_metrics` | VERIFIED | Passed |
| GRF-2 | Versions and reload | P0 | Graph, question, and search history survive a new process | `database.py` `load_export` | `test_story_c_survives_reload_without_new_external_calls` | VERIFIED | Passed. Zero external calls |
| GRF-3 | Shared origin | P0 | Four Story C documents form one `LF-PR-2026-031` cluster | `verification.py` `classify_provenance` | Story C test | VERIFIED | 1 original, 3 derivatives |
| GRF-4 | Shared origin is not sufficiency | P0 | The loop does not stop as `evidence_sufficient` because derivatives repeat the amount | `orchestrator.py` `run_story_c` | Story C helper | VERIFIED | Stop is `unresolved_uncertainty` with an independence question |
| GRF-5 | Contradiction | P0 | `$480 million` is contradicted and `$400 million` on the original stays supported | `verification.py` `reconcile_amount_conflicts` | Story C test | VERIFIED | Passed |
| GRF-6 | Export provenance | P0 | API export still contains spans and provenance | `main.py` export route | `test_api_export_exposes_graph_and_quotes` | VERIFIED | Passed |
| LOOP-1 | Controller approval | P0 | A usable approval runs that query and records `convergence` | `convergence.py`, `orchestrator.py` | `test_controller_approval_executes_and_malformed_payload_does_not` | VERIFIED | Passed |
| LOOP-2 | Malformed controller body | P0 | A non-object body is `fallback` and is not treated as the controller action | `convergence.py` `evaluate_controller` | `test_malformed_controller_payload_is_rejected` | VERIFIED | Passed |
| LOOP-3 | Duplicate follow-up | P0 | A query already in search history is not sent again | `orchestrator.py` lines 327–331 | `test_duplicate_controller_query_is_not_executed` | FAILED | Same query searched twice |
| LOOP-4 | Original question | P0 | The stored question cannot be replaced | `graph.py` `save` | reload test | VERIFIED | `ValueError` on rewrite |
| LOOP-5 | Fallback when the controller is down | P0 | Connection failure is labeled `fallback` | `planner.py` `fallback_decision` | Story C test with a down post | VERIFIED | `decision_source` is `fallback` |
| CHK-1 | Counters after restore | P0 | `searches_used` and search history match after reopen | `database.py` | reload test | VERIFIED | Passed |
| DEMO-1 | Story C metrics | P0 | B3 counts match the export; B0 does not claim the origin or the contradiction; network calls stay 0 | `baseline.py` | Story C test | VERIFIED | Passed |
| DEMO-2 | Story A recorded run | P0 | The written rationale matches the run, and supported rows are distinct grounded facts | `demo/evaluation.json`, `cold/story.sqlite` | consistency test plus read-only audit of `inv_8e46a18764e64eb0` | FAILED | Rationale matches the fallback. The 6 rows are 2 facts on 3 pages, not 6 distinct relationships. See `qa/release_report.md` |
| DEMO-3 | Live Telem smoke | P0 | One authorized live search | `retrieval.py` `_sdk_search` | not run | IMPLEMENTED / UNVERIFIED | QA did not spend a live call. The committed demo file records an earlier search |
| UI-1 | Clickable graph | P0 | A frontend can open a relationship and its quotation | no React app | API export test | NOT IMPLEMENTED | Export has the data. `exploration/README.md` says there is no React UI |
| P2-1 | Domain routing and monitoring | P2 | Specialist policies and continuous source checks | none | none | NOT IMPLEMENTED | Out of the committed package |
