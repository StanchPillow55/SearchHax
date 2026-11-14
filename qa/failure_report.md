# Failure report

## BLOCKER — The web loop labels a shared wire and then drops the cluster and the contradiction

Requirement: pages that cite one announcement are one origin, and a derivative amount is not stored as a second supported fact. `run_story_c` does this. The search/fetch loop does not.

Snapshot: implementation `8e3e6e5`.

Reproduction:

```text
/Users/bradleyharaguchi/SearchHax/exploration/.venv/bin/python -m pytest qa/tests/test_provider_and_budget.py::test_web_path_keeps_story_c_wire_as_one_origin_and_one_amount --tb=short -p no:cacheprovider --override-ini=testpaths=qa/tests
```

One mocked search returns `https://lumenarc.example/press/series-d` (`FOR IMMEDIATE RELEASE`, `$400 million`, `LF-PR-2026-031`) and `https://voltstreet.example/lumenarc` (`$480 million`, same wire). No live provider is called.

Expected: `origin_clusters` contains `LF-PR-2026-031` with both documents, `$400 million` stays `supported`, and `$480 million` is not `supported`.

Actual: the test fails because `origin_clusters` is empty. The provenance rows are already `original` and `derivative` with `origin_id` `LF-PR-2026-031`. Both `raised_amount` edges are `supported`, and `contradictions` is empty.

Location: `exploration/backend/orchestrator.py` `_ingest_bundle` calls `classify_provenance` for `.example` URLs around lines 482–493. `origin_clusters` and `reconcile_amount_conflicts` are called only from `run_story_c` at lines 160 and 159.

Deterministic: yes.

Suggested correction: after web ingest, build the origin clusters from the provenance rows and run the same amount reconciliation used by Story C.

## BLOCKER — A causal demand sentence closes the gap without evidence

Requirement: a link from the investment to future product demand is a hypothesis until separate evidence supports it. Naming demand in a causal sentence is not that evidence, and it does not answer the open demand question.

Snapshot: implementation `8e3e6e5`.

Reproduction:

```text
/Users/bradleyharaguchi/SearchHax/exploration/.venv/bin/python -m pytest qa/tests/test_provider_and_budget.py::test_causal_demand_sentence_does_not_close_the_gap --tb=short -p no:cacheprovider --override-ini=testpaths=qa/tests
```

The fetched page is: `NVIDIA has invested $2 billion in CoreWeave. That investment caused customer demand for AI factories to rise.` No live provider is called. The controller is down.

Expected: the demand question stays open, or a demand relationship is stored as `hypothesis` or `insufficient`. No causation edge is `supported`.

Actual: `unresolved_questions` is empty and there is no demand relationship. `invested_in` and `invested_amount` are `supported`. The next fallback step stops with `no_useful_actions` because nothing is left to ask.

Location: `exploration/backend/extraction.py` line 267 treats any match of `customer demand`, `downstream demand`, or `product revenue` as demand already stated, so the gap at lines 268–276 is skipped. The causal sentence is never stored.

Deterministic: yes.

Suggested correction: keep the demand question open unless a grounded, non-causal measurement of demand is extracted. If the causal sentence is stored, its status is `hypothesis`, not `supported`.

## BLOCKER — A denial that contains the investment wording becomes supported

Requirement: unsupported assertions do not become supported graph edges. A quotation has to keep the sentence that qualifies it. Preserving only the matching clause drops the denial.

Snapshot: implementation `8e3e6e5`.

Reproduction:

```text
/Users/bradleyharaguchi/SearchHax/exploration/.venv/bin/python -m pytest qa/tests/test_provider_and_budget.py::test_negated_investment_sentence_is_not_supported --tb=short -p no:cacheprovider --override-ini=testpaths=qa/tests
```

The fetched page is: `The rumor that NVIDIA has invested $2 billion in CoreWeave is unconfirmed and is not in the filing.` No live provider is called.

Expected: no relationship from that page has status `supported`.

Actual: `invested_amount` `$2 billion` and `invested_in` `CoreWeave` are both `supported`. The stored span text is `NVIDIA has invested $2 billion in CoreWeave`, which is an exact substring, and the words `rumor` and `unconfirmed` are not in the span.

Location: `exploration/backend/extraction.py` line 236 matches that clause. `_extract_disclosed_facts` at line 252 passes only `match.group(0)` to `_add_grounded`. `decide_status` then marks the clause supported because `NVIDIA` and `CoreWeave` occur inside it. The surrounding sentence is not checked.

Deterministic: yes.

Suggested correction: do not mark a match supported when the enclosing sentence negates or qualifies it (`rumor`, `unconfirmed`, `not in the filing`). Store the enclosing sentence as the span, or downgrade the edge to `insufficient`.

## BLOCKER — The web loop accepts two contradictory amounts as supported

Requirement: contradictory claims are not accepted together without qualification. Provenance verification labels conflict. Story C does this. A normal web investigation does not.

Snapshot: implementation `8e3e6e5`.

Reproduction:

```text
/Users/bradleyharaguchi/SearchHax/exploration/.venv/bin/python -m pytest qa/tests/test_provider_and_budget.py::test_web_path_does_not_accept_two_amounts_as_supported --tb=short -p no:cacheprovider --override-ini=testpaths=qa/tests
```

One mocked search returns two pages. One says `NVIDIA has invested $2 billion in CoreWeave.` The other says `NVIDIA has invested $5 billion in CoreWeave.` Both quotations match the stored page text. No live provider is called.

Expected: a contradiction is recorded, or the two `invested_amount` edges are not both `supported`.

Actual: both edges are `supported`, `contradictions` is empty, and each edge's notes are empty.

Location: `exploration/backend/orchestrator.py` calls `reconcile_amount_conflicts` only from `run_story_c` (line 159). `_ingest_bundle` appends relationships and never reconciles them. Web pages that are not `*.example` are stored with `origin_kind` `unknown` at lines 485–491, so even a later reconcile would not know which page is the original.

Deterministic: yes.

Suggested correction: after web extraction, run the same conflict check used for Story C. Do not leave two different amounts for the same subject and predicate `supported` with an empty contradiction list.

## BLOCKER — A total provider outage stays `running` and drops the error

Requirement: network failures are handled explicitly. A search where every provider fails must stop, and the failure must be visible on the investigation. It must not invent documents.

Snapshot: implementation `8e3e6e5`.

Reproduction:

```text
/Users/bradleyharaguchi/SearchHax/exploration/.venv/bin/python -m pytest qa/tests/test_provider_and_budget.py::test_provider_outage_is_recorded_and_the_investigation_stops --tb=short -p no:cacheprovider --override-ini=testpaths=qa/tests
```

The mocked search returns Brave status 503 `unavailable` and Tavily status 429 `rate limit`, both with empty results. No fetch runs. No live provider is called.

Expected: `status` is `stopped`, and `blocker`, `stop_reason`, or `decision_rationale` names the 503, the 429, or the provider error text. `documents` and `relationships` stay empty.

Actual: `status` is `running`, `stop_reason` is null, `blocker` is null, and `decision_rationale` is empty. `documents` and `relationships` are empty. One search was consumed.

Location: `exploration/backend/retrieval.py` keeps the failures on `SearchBundle.provider_errors`, and the stored `raw.provider_runs` at lines 396–405 keep provider and status but drop `error`. `exploration/backend/orchestrator.py` `_initial_web_step` lines 292–310 only stops when `live_extraction_blocked` is set. An empty result set never sets that flag, so the outage is discarded and the investigation stays `running`.

Deterministic: yes.

Suggested correction: when `provider_errors` is non-empty and no document content was stored, set `blocker` to those errors, set status to `stopped`, and set `stop_reason` to `unresolved_uncertainty`.

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

Requirement: an unresolved important relationship generates a follow-up, and the convergence path can approve that action. Marking the four known articles as `consider` is not a reason to cancel a search for a source outside that set.

Snapshot: implementation `2c8133a`. Retested after importing that commit. On `8e3e6e5` the same test failed because every candidate was archived with `low_expected_value`. The new ranker no longer archives them. It still does not approve the search.

Reproduction:

```text
/Users/bradleyharaguchi/SearchHax/exploration/.venv/bin/python -m pytest qa/tests/test_focus_and_versions.py::test_focus_approves_the_story_c_independence_search --tb=short -p no:cacheprovider --override-ini=testpaths=qa/tests
```

The Story C run builds one open question, importance 0.9 and missing evidence 1.0, and one unused action whose utility is 0.9. The query contains `independent primary confirmation of the Lumenarc Dynamics Series D amount` and `LF-PR-2026-031`. `evaluate_with_focus` is called with that request. No network call is made.

Expected: `stop` is false and `approved_action.query` contains `LF-PR-2026-031`.

Actual: `stop` is true, `stop_reason` is `unresolved_uncertainty`, and `approved_action` is null. All four candidates are `consider` with reason `eligible evidence candidate (not verified truth)`. The rationale begins `Focus marked candidates for consideration and did not request another search.`

Location: `exploration/backend/focus_bridge.py` lines 85–99. The approval branch at lines 69–84 runs only when some passage is `investigate`. The `consider` branch sees the open question and returns a stop without reading `proposed_actions`.

Deterministic: yes. `python -m unittest test_focus_attention.py` from `focus/` passes 12 tests. Those tests do not cover this handoff.

Suggested correction: when a pending action's utility is at least `budget.min_utility`, approve that action even if the current pages are only `consider`. Those pages are the shared-origin set. The follow-up exists to look outside it.

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
