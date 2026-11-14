# Release report

Commit tested: `c81ea8e` on `feat/exploration`, imported as `c371a0a` on `qa/exploration-verification`.

QA command:

```text
/Users/bradleyharaguchi/SearchHax/exploration/.venv/bin/python -m pytest qa/tests -q --tb=line -p no:cacheprovider --override-ini=testpaths=qa/tests
```

Exit status 1. 15 passed, 2 failed. No new Telem, Tavily, or LLM credit was spent. Story A evidence was read from the existing database `/Users/bradleyharaguchi/SearchHax/exploration/data/cold/story.sqlite`, investigation `inv_8e46a18764e64eb0`.

Recommendation: **READY WITH DISCLOSED LIMITATIONS**

The recorded Story C demo and the stored Story A investigation can be shown. Do not present the six Story A rows as six distinct findings, and do not present a live Convergence decision. Convergence is not available in this workspace.

## P0 results

| Requirement | Result | Evidence |
| --- | --- | --- |
| Follow-up save survives a repeated entity | PASS | `test_repeated_entity_on_follow_up_does_not_crash` passed. Duplicate ids are skipped in `database.py` lines 341–345. |
| Duplicate follow-up query is not searched again | FAIL | `test_duplicate_controller_query_is_not_executed` failed. `orchestrator.py` lines 332–338 still search the approved query with no history check. |
| Demo record no longer blames a missing LLM key | PASS | `demo/evaluation.json` rationale is the `RemoteProtocolError` fallback. `llm_calls` is 2. The old missing-key sentence is gone. |
| Six Story A rows are exact quotations | PASS | All 6 links match the stored page slice. The quotation is `NVIDIA has invested $2 billion in CoreWeave`. |
| Six Story A rows are semantically distinct | FAIL | 6 rows, 2 facts, 3 pages, 3 spans, 1 sentence. Each span emits both `invested_in` CoreWeave and `invested_amount` $2 billion. |
| Story A replay without new retrieval | PASS | Resume of `inv_8e46a18764e64eb0` returned `network_fetches: 0`, `unchanged_versions: 5`, and the provider stubs were not called. Search history stayed at 2 queries. |
| Story A extraction mode | PASS as a finding | The 6 edges come from deterministic `disclosed_facts` (`extraction.py` line 236). The LLM was used only on the two pages that lack that sentence and added no supported edge. |
| Fresh live Story A | BLOCKED | Not run again, so no extra provider credits were spent. |
| Story C shared origin | PASS | `test_story_c_provenance_contradiction_and_metrics` passed. One cluster, `LF-PR-2026-031`, 1 original and 3 derivatives. |
| Story C planted contradiction | PASS | `$480 million` is contradicted. The original `$400 million` stays supported. Stop is `unresolved_uncertainty`. |
| Checkpoint resume does no extra retrieval | PASS | Same resume result as Story A, and the Story C reload test passed. |
| Exploration–Convergence integration | BLOCKED | Nothing in the repo serves the controller. Port 8000 is `python3 -m http.server`. `POST /api/convergence/evaluate` returned an empty reply. The stored Story A decision is `fallback` because of `RemoteProtocolError`. |
| Unresolved gap changes which page is fetched | FAIL | `test_unresolved_gap_changes_which_page_is_fetched` failed. `orchestrator.py` line 431 passes no gap list into `score_passage`. |
| Clickable graph UI | FAIL | No React app. The API export and CLI contain the graph. |

## Blocking failures to send to the implementation agent

### 1. A repeated controller query is still executed

Deterministic. Requirement: do not search a query that is already in search history.

Reproduction:

```text
/Users/bradleyharaguchi/SearchHax/exploration/.venv/bin/python -m pytest qa/tests/test_evidence_and_loop.py::test_duplicate_controller_query_is_not_executed --override-ini=testpaths=qa/tests
```

The first search is `alpha beta gamma delta`. The controller approves that same string with `stop: false`. Expected: one provider call. Actual: `['alpha beta gamma delta', 'alpha beta gamma delta']`.

Where: `exploration/backend/orchestrator.py` lines 332–338.

Correction: if `decision.approved_action.query` is already in `search_queries`, do not call `retrieval.search`.

### 2. Do not present the six Story A rows as six distinct relationships

Deterministic for the stored run. Grounding is correct. Distinctness is not.

Reproduction: open `exploration/data/cold/story.sqlite`, investigation `inv_8e46a18764e64eb0`. The six supported links use three spans and one sentence, `NVIDIA has invested $2 billion in CoreWeave`, on these pages:

- `https://www.coreweave.com/news/nvidia-and-coreweave-strengthen-collaboration-to-accelerate-buildout-of-ai-factories`
- `https://investors.coreweave.com/news/news-details/2026/NVIDIA-and-CoreWeave-Strengthen-Collaboration-to-Accelerate-Buildout-of-AI-Factories/default.aspx`
- `https://futurumgroup.com/insights/nvidia-and-coreweave-team-to-break-through-data-center-real-estate-bottlenecks`

Each span has both `invested_in` / CoreWeave and `invested_amount` / `$2 billion`. `demo/evaluation.json` reports `supported_relationships: 6` and its Story A note does not say these are 2 facts on 3 pages. `shared_origin_detected` is false, so the company page and the investor page are not grouped.

Expected: the demo count distinguishes unique facts from repeated attestations, and pages that repeat one announcement are not treated as independent confirmations.

Correction: report 2 grounded facts attested on 3 pages. The walkthrough already says this. Put that breakdown in `demo/evaluation.json` as well. `extraction.py` lines 252–268 create both predicates from the same match.

### 3. Fetch ranking still ignores the open gap

Deterministic.

Reproduction:

```text
/Users/bradleyharaguchi/SearchHax/exploration/.venv/bin/python -m pytest qa/tests/test_evidence_and_loop.py::test_unresolved_gap_changes_which_page_is_fetched --override-ini=testpaths=qa/tests
```

One fetch slot remains. The gap page is `https://example.com/gap` with snippet `zeta quantum lattice`. The fetched URL is `https://example.com/query-only`.

Where: `exploration/backend/orchestrator.py` line 431.

Correction: pass the open question texts into `score_passage`.
