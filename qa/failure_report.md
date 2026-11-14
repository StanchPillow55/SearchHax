# Failure report

## BLOCKER — A controller stop without a reason code leaves the investigation running

Requirement: a valid controller response leads to the corresponding action. `stop: true` ends the investigation, so status becomes `stopped`.

Snapshot: implementation `8e3e6e5`.

Reproduction:

```text
/Users/bradleyharaguchi/SearchHax/exploration/.venv/bin/python -m pytest qa/tests/test_focus_and_versions.py::test_controller_stop_without_reason_code_still_stops --tb=short -p no:cacheprovider --override-ini=testpaths=qa/tests
```

The first step retrieves one mocked page containing `NVIDIA has invested $2 billion in CoreWeave.` The second step posts to a controller that returns `{"stop": true, "rationale": "controller says stop without a reason code"}`. No live provider is called.

Expected: `status` is `stopped` and `stop_reason` is set. A third step does not search.

Actual: `decision.stop` is true, `decision.decision_source` is `convergence`, `decision.stop_reason` is null, and `investigation.status` stays `running`. The third step also stays `running`. The provider was called once.

Location: `exploration/backend/convergence.py` line 87 stores `stop_reason` only when the code is one of the five literals, so a missing code becomes null. `exploration/backend/orchestrator.py` line 355 applies the stop only when both `decision.stop` and `decision.stop_reason` are set. The same conjunction is at line 237 for Story C. A later step returns immediately only when status is already `stopped` or `blocked`.

Deterministic: yes.

Suggested correction: when `decision.stop` is true, set status to `stopped`. If the payload omitted a known reason, record `unresolved_uncertainty` rather than dropping the stop.

## BLOCKER — Focus handoff refuses the Story C independence search

Requirement: an unresolved important relationship generates a follow-up, and the convergence path can approve that action. Archiving the four known articles is not a reason to cancel a search for a source outside that set.

Snapshot: implementation `8e3e6e5`. QA file `qa/tests/test_focus_and_versions.py`.

Reproduction:

```text
/Users/bradleyharaguchi/SearchHax/exploration/.venv/bin/python -m pytest qa/tests/test_focus_and_versions.py::test_focus_approves_the_story_c_independence_search --tb=short -p no:cacheprovider --override-ini=testpaths=qa/tests
```

The Story C run builds one open question, importance 0.9 and missing evidence 1.0, and one unused action whose utility is 0.9. `evaluate_with_focus` is then called with that request. The default HTTP path is not involved. No network call is made.

Expected: `stop` is false and `approved_action.query` contains `LF-PR-2026-031`.

Actual: `stop` is true, `stop_reason` is `low_expected_value`, and `approved_action` is null. The rationale is `Focus archived every candidate` for all four Story C candidate ids. The same shape is already stored in `demo/integration/story_c_focus_decision.json`.

Location: `exploration/backend/focus_bridge.py` lines 54–84. `FocusAttentionModel.decide` archives a passage whose lexical overlap with the original question is under 0.20. `evaluate_with_focus` treats "every candidate archived" as a stop and never reads `proposed_actions` in that branch.

Deterministic: yes.

Suggested correction: when a pending action's utility is at least `budget.min_utility`, approve that action even if the pages already in hand are archived. Those pages are the shared-origin set. The follow-up exists to look outside it.

The fallback path is separate and still runs this follow-up. `run_story_c` with a down controller records `decision_source=fallback` and keeps the independence question. This blocker is the focus handoff, not that fallback.

## Earlier snapshot

The `8e3e6e5` offline suite aside from the test above had no blocking failures.

Command: `/Users/bradleyharaguchi/SearchHax/exploration/.venv/bin/python -m pytest exploration/tests qa/tests -m "not integration" -q --tb=line -p no:cacheprovider --override-ini=testpaths=`

Result: 53 passed, 2 live tests deselected, exit status 0. `python -m unittest test_focus_attention.py` from `focus/` : 5 passed. No Telem, Tavily, or LLM call was made.

The entity-save crash, duplicate controller query, gap-ranking miss, and inconsistent Story A rationale from `edf9e32` stay closed. No new blocker showed up in the focus handoff (`72dfbe1`, `0c04abe`, `8e3e6e5`).

Earlier findings:

Current release findings below were for commit `c81ea8e`. The entity-save crash and the missing-key demo rationale from `edf9e32` were closed before `ec31c60`. The duplicate-query and gap-ranking failures were open at `c81ea8e` and closed by `ec31c60`. The six Story A rows are two facts on three pages.

Snapshot: `edf9e32` (`feat/exploration`, "Record the exploration investigation milestone").

QA command: `/Users/bradleyharaguchi/SearchHax/exploration/.venv/bin/python -m pytest qa/tests -q --tb=line -p no:cacheprovider --override-ini=testpaths=qa/tests`

Result: 4 failed, 13 passed, exit status 1. No live Telem or Tavily call was made.

## BLOCKER — Follow-up save crashes when an entity id already exists

Requirement: structured extraction failures and later investigation steps must not crash the investigation. A second document that names an entity already in the graph must merge.

Reproduction:

```text
qa/tests/test_evidence_and_loop.py::test_repeated_entity_on_follow_up_does_not_crash
```

Two fetched pages both contain `NVIDIA invested $2 billion in CoreWeave.` The mocked extractor returns the same NVIDIA and CoreWeave entities for each page. The first step saves. The second step raises.

Expected: the follow-up is saved, and `NVIDIA` occurs once in the entity list.

Actual: `sqlite3.IntegrityError: UNIQUE constraint failed: entities.investigation_id, entities.id`.

Location: `exploration/backend/orchestrator.py` line 494 appends entities with `export.entities.extend` and does not drop ids already on the export. `exploration/backend/database.py` line 342 inserts every row. Entity ids come from `stable_id("ent", type, name)` in `exploration/backend/extraction.py` and are shared across documents.

Deterministic: yes.

Suggested correction: upsert entities by id before `replace_graph_rows`, or skip ids that are already stored for that investigation.

## BLOCKER — An already executed query is searched again

Requirement: duplicate follow-up queries are avoided, and the hard search budget is not spent twice on the same query.

Reproduction:

```text
qa/tests/test_evidence_and_loop.py::test_duplicate_controller_query_is_not_executed
```

The first step searches `alpha beta gamma delta`. The controller then approves that same string with `stop: false` and a rationale. The second step calls the provider again.

Expected: the repeated query is not sent. The recorded decision stays on the controller, and `searches_used` does not increase for that repeat.

Actual: the provider is called twice with `['alpha beta gamma delta', 'alpha beta gamma delta']`.

Location: `exploration/backend/orchestrator.py` lines 327–331 execute `decision.approved_action.query` without checking `search_queries`. `generate_actions` in `exploration/backend/planner.py` skips duplicates, but the controller path does not.

Deterministic: yes.

Suggested correction: if the approved query is already in search history, do not call `retrieval.search`. Keep `decision_source` as `convergence` and record that the action was already executed.

## BLOCKER — Committed Story A demo record contradicts itself

Requirement: Story A works from retrieved evidence, and no fabricated citation or metric is presented. A missing key must not be reported when extraction actually ran.

Reproduction: read `demo/evaluation.json` in commit `edf9e32`.

```text
qa/tests/test_evidence_and_loop.py::test_committed_story_a_record_is_internally_consistent
```

Expected: a recorded live run either extracts supported relationships from the fetched pages, or its rationale matches the real blocker. With `llm_configured: true` and `llm_calls: 5`, the rationale does not say the key is missing.

Actual:

- `story_a.blocker` is `LLM extraction failed: ReadTimeout`
- `story_a.llm_configured` is true and `usage.llm_calls` is 5
- `story_a.decision_rationale` says live extraction is blocked because no LLM key is configured
- `story_a.relationships` is `[]`
- `reports` for Story A repeats `latency_ms: 0` and `supported_relationships: 0`

Location: `demo/evaluation.json` lines 4–19 and the Story A report at lines 100–124. The current stop path at `exploration/backend/orchestrator.py` lines 296–298 stores `investigation.blocker` instead of that missing-key sentence, so this file does not match the code in the same commit.

Deterministic: yes for the committed file. This QA pass did not repeat the live search.

Suggested correction: regenerate `demo/evaluation.json` from the current code. Keep the ReadTimeout blocker if that is what the run did. Remove the missing-key rationale. Do not fill relationships that were not extracted. A Story A demo still needs a later run whose stored quotations support the NVIDIA relationships.

## HIGH — Unresolved gaps do not change which page is fetched

Requirement: unresolved graph gaps influence passage ranking.

Reproduction:

```text
qa/tests/test_evidence_and_loop.py::test_unresolved_gap_changes_which_page_is_fetched
```

One fetch slot remains. The follow-up returns `https://example.com/query-only` (snippet `alpha beta`, query overlap only) and `https://example.com/gap` (snippet `zeta quantum lattice`, the open gap). `score_passage` ranks the gap page higher when the gap list is passed. The fetch receives the query-only URL.

Expected: the fetched URL is `https://example.com/gap`.

Actual: the fetched URL is `https://example.com/query-only`.

Location: `exploration/backend/orchestrator.py` line 426 calls `score_passage` with the gap list set to `None`.

Deterministic: yes.

Suggested correction: pass the open question texts into `score_passage` when ranking snippets for fetch.
