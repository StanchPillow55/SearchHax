# Release candidate

Latest import: `8e3e6e5` on `feat/exploration` / `main`. QA merge: `6dab401`.

Offline result on that commit: 53 passed, 2 live tests deselected, exit status 0. Focus ranker unit tests: 5 passed. No blocking failures. The notes below still describe the `ec31c60` pass and remain true for the checks they name.

Tested implementation commit for the previous pass: `ec31c60` on `feat/exploration`.

QA import: `4a5d009` on `qa/exploration-verification`.

Command, using `/Users/bradleyharaguchi/SearchHax/exploration/.venv`:

```text
python -m pytest exploration/tests qa/tests -m "not integration" -q --tb=line -p no:cacheprovider --override-ini=testpaths=
```

Result: 49 passed, 2 deselected, exit status 0. The two deselected tests are the live Telem integration tests. This run made no Telem, Tavily, or LLM call.

Decision: **READY WITH DISCLOSED LIMITATIONS**

The duplicate-query and gap-ranking regressions from `c81ea8e` pass on this commit. Story C, checkpoint reuse, quote grounding, and the entity-save regression pass. Convergence was not running, so this is not a verified controller integration.

## Checks

| Check | Result | Evidence |
| --- | --- | --- |
| Duplicate controller query is not searched again | PASS | `test_duplicate_controller_query_is_not_executed`. `orchestrator.py` lines 332–338 skip a query already in search history. |
| Unresolved gap changes the fetched page | PASS | `test_unresolved_gap_changes_which_page_is_fetched`. `orchestrator.py` lines 437–438 pass open question text into `score_passage`. |
| Story A unique facts vs attestations | PASS in the written demo, with a JSON limitation | Stored run `inv_8e46a18764e64eb0`: 2 unique facts, 6 attestations, 3 pages. `demo/walkthrough.md` lines 17–20 and `exploration/IMPLEMENTATION_STATUS.md` state that split. `demo/evaluation.json` `supported_relationships` is still 6 and its note does not repeat the split. |
| Quotations match stored pages | PASS | All 6 Story A links match `content[start:end]`. `bad_quotes` is 0. Story C quote tests passed. |
| Entity-integrity regression | PASS | `test_repeated_entity_on_follow_up_does_not_crash`. |
| Story C shared origin and contradiction | PASS | `test_story_c_provenance_contradiction_and_metrics` and the API export test. |
| Checkpoint reuse makes no new retrieval | PASS | `test_story_c_survives_reload_without_new_external_calls`. |
| Non-integration suite | PASS | 49 passed, 2 live tests deselected. |
| Live Convergence end-to-end | BLOCKED | Listeners are Jupyter on 8888, Tomcat on 8080, and `python3 -m http.server` on 8000. None is the convergence controller. No contract request was sent. |

## Disclosed limitations

- The stored Story A decision is `fallback` after `RemoteProtocolError`. A live controller response was not verified.
- There is no React graph UI. The CLI and HTTP export are the surface.
- The six Story A edges come from the deterministic sentence matcher, not from model JSON. Local Ollama calls are not sent unless `LLM_FORCE_LOCAL=1`.
- `supported_relationships: 6` in `demo/evaluation.json` counts attestations. The unique facts are NVIDIA `invested_in` CoreWeave and NVIDIA `invested_amount` `$2 billion`.
- This QA pass did not repeat the live Telem search.

## Remaining blockers

No critical workflow failure remains in the tested commit. The open item is the missing Convergence service, which blocks an integration claim and does not block the offline Story C demo or the stored Story A replay.
