# SearchHax — M0/M1 verification and M2 plan

Audit date: 2026-11-20. Worktree: `../SearchHax-frontend`, branch `frontend/react-integration` at `6d996c2`.
No billable provider call was made. Provider keys were stripped from the environment for every test run.
The API under test ran on `127.0.0.1:8010` against a **copy** of `exploration/data/exploration.sqlite`.

---

## 1. Git baseline and integration recommendation

| Ref | Relation to `origin/main` (754881f) | Pushed? | Notes |
|---|---|---|---|
| `main` (local) | +4, −0 | no | `bb41494` cited answer, `83eec46` Streamlit UI, `ece7a3c` merge, `e8a1f68` JSON hardening |
| `lantern-trace-workspace` | +6, −0 | no | adds `1c58e82` trace/branching/context space, `2232223` Figma prototype |
| `frontend/react-integration` | **+8, −0** | no | adds `52835d9` API listing/attachments, `6d996c2` React frontend |
| `integrate/knowledge-value` | +0, −26 | yes | already fully contained in `origin/main` |
| `qa/exploration-verification` | +92, −0 (81 unpushed) | partly | defect ledger: tests that record known defects |
| `feat/exploration` | +1, −0 | yes | contained in `origin/main` history |

Findings

- `frontend/react-integration` is a **strictly linear** descendant of `origin/main`: 0 commits behind. A PR to `main` fast-forwards and carries all 8 commits, with their full dependency chain. Nothing needs to be cherry-picked.
- All four worktrees are clean. The only uncommitted change anywhere is `.claude/launch.json` in the main checkout (a local dev-server entry).
- Trial merge of `qa/exploration-verification` into `frontend/react-integration` (`git merge-tree` and a throwaway worktree):
  - The merge is clean, but 7 files overlap (`answer.py`, `database.py`, `llm.py`, `main.py`, `test_llm_json.py`, `focus/ui_backend.py`, `shared/contracts.py`).
  - Backend results are identical before and after the merge (112 pass / 4 fail).
  - QA results are identical (35 pass / 59 fail / 1 collection error).
- Secret scan of the 8-commit diff: no keys or tokens. No `.env`, SQLite, `node_modules` or `dist` is tracked. The only `.env*` file is `frontend/.env.example`, which has placeholders and no values.
- There is **no CI** (`.github/workflows` does not exist).

Recommendation

1. Push `frontend/react-integration` and open **one PR into `main`** containing all 8 commits. Do not cherry-pick the top two commits: they depend on `1c58e82` (trace and branch API) and on `bb41494` (`answer.py`).
2. Keep `qa/exploration-verification` as a separate defect-ledger branch. Do not merge it until its recorded defects are fixed or explicitly accepted; merging it now would turn `main` red with 59 intentional failures.
3. Add CI (M0 remainder) as follows:
   - `pytest -m "not integration"` with the provider tests deselected or skipped when no key is set.
   - `vitest`, `tsc` and `vite build`.
   - Playwright against a seeded throwaway DB.

Manual steps if the tooling cannot push:

```bash
git -C ../SearchHax-frontend push -u origin frontend/react-integration
gh pr create --repo StanchPillow55/SearchHax --base main --head frontend/react-integration --title "React frontend integrated with the exploration API (M0–M2)"
```

## 2. Verification results — M0 and M1

| Check (Phase 2) | Result | Evidence |
|---|---|---|
| 1. Investigation listing | **Pass**: 44 stored investigations come from `GET /investigations` | `m1-audit.spec.ts`, `a1-listing.png` |
| 2. Selecting an investigation | **Pass**: clicking a list row sets `?investigation=` | `m1-audit.spec.ts` |
| 3. Question and status | **Pass**: matches the export exactly ("Stopped · budget exhausted") | `1-interior-latest.png` |
| 4. Search and evidence activity | **Pass**: 11/11 recorded events; record IDs in the inspector | `vertical-slice.spec.ts` |
| 5. Source provenance | **Pass**: URL, provider, origin "unknown", version hash, fetch time, `documents · doc_…` | `2-source-provenance.png` |
| 6. Convergence decisions | **Pass**: decision node "Stop: research budget exhausted", plus a Recorded decisions list | `a2-convergence.png` |
| 7. Persisted checkpoints | **Pass**: C1/C2 with snapshot counts and step; URL `cp=` | `3-checkpoint-snapshot.png` |
| 8. Historical playback | **Pass**: seek to event 1, step forward, return to latest | `a3-playback-early.png` |
| 9. Reload | **Pass**: same question, checkpoint and event count after a full reload | `4-after-reload.png` |
| 10. Switching without leakage | **Pass**: none of A's documents or its question appear in B's workspace | `a4-switched.png` |
| Read-only journey | **Pass**: every `/api/` request on the M1 journeys was a `GET` | both specs |
| Demo isolation | **Pass**: demo mode makes 0 `/api/` requests and shows a "simulated" ribbon | `vertical-slice.spec.ts` |

Verdict

- **M1 is verified against the live API, not fixtures.**
- **M0 is complete except for push, PR and CI**, which need your go-ahead or a later step.

Screenshots: `docs/audit/screenshots/`.

## 3. Real versus simulated feature matrix

| Feature | Live mode | Source |
|---|---|---|
| Investigation list, picker, recent | Real | `GET /investigations` (+ local `recent` list) |
| Interior: rounds, searches, sources, passages, claims, open questions | Real | `/trace` + export. "Rounds" are **derived** groupings and are labelled as such |
| Timeline playback, checkpoints, snapshot view | Real | `trace.events`, `checkpoint.state_json.snapshot` |
| Inspector provenance | Real | `provenance`, `document_versions`, `evidence_links` |
| Checkpoint compare | Real | two persisted snapshots |
| 3D Evidence Space | Real | `checkpoint.state_json.policy_space` (one point per **document**, not per passage) |
| Constellation (lineage) | Real | `/branches`, walked recursively |
| Save Lantern (create branch) | Real, local write, no provider calls | `POST /investigations/{id}/branches` |
| Start research on a branch | Real, but **gated off** (`VITE_ALLOW_BILLABLE_RESEARCH` plus a confirmation checkbox) | `POST /branches/{id}/resume` |
| New investigation | **Missing** in live mode (button disabled) | `POST /investigations` exists but isn't wired |
| Findings / cited answer view | **Missing** in live mode (demo only) | `POST /investigations/{id}/answer` exists (billable LLM) |
| Parent ↔ child Lantern compare | **Missing** in live mode (demo only) | needs a diff endpoint or a client diff |
| Personal knowledge workspace | **Missing** in live mode (demo only) | `GET /profile/knowledge-graph`, `POST /profile/knowledge-assertions` exist |
| Search & history | **Missing** in live mode (demo only) | n/a |
| Everything in Demo mode | Simulated, labelled with a ribbon | `src/trace/data.ts`, `App.tsx` |

## 4. Tests

| Suite | Result |
|---|---|
| `tsc --noEmit` | pass |
| `vitest` | **57 / 57** pass |
| `vite build` | pass (bundle-size warning only) |
| Playwright (live API on :8010) | **6 / 6** pass (`vertical-slice` 3, `branching` 2, `m1-audit` 1 — new) |
| Backend `pytest -m "not integration"` | **117 pass, 4 fail, 5 xfail** (includes the 10 new regression tests) |
| Same backend suite on `origin/main` | 81 pass, 3 fail |

The 4 backend failures

- 3 need `TAVILY_API_KEY`, and they fail identically on `origin/main`:
  - `test_integrated_pipeline` ×2
  - `test_tavily_retrieval::test_missing_api_key_uses_keyless_search_and_extract`
- 1 was introduced on this lineage and is environment-specific: `focus/test_context_space.py::test_installed_streamlit_discards_scatter3d_clicks_without_parent_id`. It greps the installed Streamlit bundle for `PlotlyChart*.js`, and Streamlit 1.37.1 doesn't ship that file. It should skip when the bundle isn't found.

## 5. Missing API fields and compatibility gaps

- **Lifecycle**:
  - `InvestigationStatus` is `created | running | stopped | blocked`. There is no `saved`, `queued`, `failed` or `completed`.
  - A newly saved branch is stored as `running` with zero searches.
- **Question vs objective**: for `fork` and `challenge_evidence`, `create_branch` writes the objective into `investigation.question`. The child has no `root_question` / `parent_question` field.
- **Rounds**: there is no round or iteration id on events. The frontend derives rounds from search events.
- **Event lineage**: there is no `caused_by` / `prompted_by_question_id` on search events. "Why was this search run" can't be traced to the unresolved question that produced it.
- **Coordinates**: `policy_space` is per document. Passages share their document's coordinate.
- **Independence**: there are no considered-claim or independence-count fields. The UI says "independence not recorded".
- **Usage vs events**: `usage.llm_calls` (6) can exceed LLM trace events (2) without the backend flagging it.
- **Live activity**: there is no SSE or progress endpoint. `/step` is synchronous, and the client timeout for resume is 300 s.
- **Idempotency**:
  - `POST /branches` and `/resume` have no idempotency key.
  - Duplicate protection exists only in the UI (a ref guard).
- **Auth**: there is no authentication and no user/profile scoping on any route. CORS is limited to local origins.

## 6. M2 — context-loss defect: findings

The persisted record reproduces the defect:

```
inv_93606fb27bb74f3c  "How do NVIDIA's investments, ... reinforce one another?"   (parent)
└─ inv_c07010e29b434741  fork, objective "Is this true?"     → question = "Is this true?"
   └─ inv_390477badbf24e65  challenge_evidence, objective "" → search query "Is this true?"
```

| Requirement | Status today |
|---|---|
| Original research question preserved | **Not met.** `trace.py:270–273` sets `question = objective or parent.question` for fork and challenge. |
| Branch objective stored separately | Partially met: it's in `branches.objective` and `metadata.objective`, but it also overwrites the question. |
| Selected claims and sources reach query planning | **Not met.** They're validated and stored (`52835d9`), but `_challenge_step` searches `metadata.objective` verbatim (`orchestrator.py:772`). |
| Empty challenge objective cannot cause an ungrounded search | **Not met.** `""` falls back to the (already vague) question. |
| Saved vs running distinguished | **Not met.** A saved child is `running` with 0 searches. The UI infers "saved" from the absence of research events. |
| Parent records unchanged | **Met.** Export and trace are byte-identical after create and resume (new test). |

Regression tests: `exploration/tests/test_branch_context_regression.py`, offline using `FakeRetrieval` with convergence stubbed.

- **5 pass**:
  - 4 `test_current_*` tests pin the defect exactly as recorded.
  - 1 invariant test covers parent immutability.
- **5 `xfail(strict=True)`** `test_m2_*` tests define the correction. Each fails today on its intended assertion; this was checked with `--runxfail`.

Production branching code was **not** changed.

## 7. M2 implementation plan

Contract (additive, `CONTRACT_VERSION` 1.1.0)

1. `Investigation.metadata.root_question` and `parent_question`, also exposed on `InvestigationTrace`. `investigation.question` for a branch **equals the root question** for every intervention type.
2. `Investigation.metadata.lifecycle` takes one of `saved | queued | researching | stopped | failed | completed`. This is kept separate from `status`, which stays the same for backward compatibility, and separate from `stop_reason`.
   - `create_branch` sets `status="created"` and `lifecycle="saved"`.
   - `step` sets `researching`.
   - The outcome then sets `stopped`, `completed` or `failed`.
3. `CreateBranchRequest` validation for `challenge_evidence`:
   - Require ≥1 `attached_claim_ids`, or an objective that passes a grounding check.
   - Grounding check: non-empty after stripping, and not a bare deictic prompt ("is this true", "verify this", "check this", …). Otherwise return 422.
4. New `planner.branch_query(root_question, objective, attached_claims, attached_sources)`:
   - Challenge → claim text plus counter-evidence framing.
   - The objective is used only when it adds terms.
   - Fork → objective resolved against the root question.
   - The planned query is recorded in the search event payload as `planned_from: {claim_ids, source_ids, objective}`.

Code

| Step | Files | Notes |
|---|---|---|
| a | `trace.create_branch` | Stop writing the objective into `question`. Compute `root_question` by walking the parent's `metadata.root_question`. Set `lifecycle`. Add the validation from item 3 (raise `ValueError` → 422). |
| b | `orchestrator._challenge_step`, `_follow_up_web_step` | Use `branch_query(...)`. Pass `root_question` (not `objective`) to the convergence controller. Add the objective as an unresolved question with `kind="branch_objective"`. |
| c | `orchestrator.step` | Set and persist `lifecycle` transitions. Map exceptions to `failed` with the error recorded; no invented results. |
| d | `trace.build_trace`, `/investigations` list | Expose `root_question` and `lifecycle`. |
| e | `shared/contracts.py`, `frontend/src/api/schemas.ts` | Additive fields, then re-capture the fixtures. |
| f | Frontend | Show `root_question` as the research question and `branch_objective` as a secondary line. Drive the "Saved, not started" and "Researching" badges from `lifecycle`, not from event inference. Composer: require a claim selection for Challenge, or show the 422 message inline. |
| g | Tests | Remove `xfail` from the 5 `test_m2_*` tests and delete the matching `test_current_*` tests. Update `test_lantern_trace.py:225,240`, which currently assert the defect (`child.question == objective`). Add vitest coverage for the new badges and validation. |
| h | Data | No migration of old rows. Legacy branches without `root_question` are resolved at read time by walking `parent_investigation_id`, and labelled "legacy branch: question was overwritten". |

Out of scope for M2: running live research (M3), SSE (M3), auth (M10/M11).

## 8. Existing unresolved defects

1. **Branch context loss** (above). High severity, blocks M2 exit.
2. **Saved branch reported as `running`**, so lifecycle is ambiguous. Medium severity.
3. **59 recorded defects on `qa/exploration-verification`**, including:
   - URL userinfo / secret published in cited answers (`test_focus_citation_userinfo`, `test_focus_userinfo`) — **security**
   - a contradicted amount labelled "supported"
   - a fetched page dropped on canonical-URL mismatch
   - a different amount archived as a duplicate
   - an idle controller leaving an investigation running
   - and others: see `qa/test_results.md` on that branch.

   One QA test also fails to collect (`No module named 'telem'`).
4. The environment-specific Streamlit test (section 4).
5. The e2e `branching.spec.ts` writes a new child on every run. It needs a disposable DB per run; the copied DB now holds three test children of `inv_93606fb27bb74f3c`.
6. In-investigation search doesn't match stage names (searching "convergence" returns nothing even though a convergence node exists).
7. A live child's header shows the overwritten question (it faithfully renders defect 1).
8. `usage.llm_calls` vs LLM trace events mismatch isn't surfaced by the backend.
9. There's no CI, no auth, and no server-side idempotency on writes.

## 9. Is it safe to begin M2?

**Yes, with one precondition:** merge (or at least push) the 8-commit integration branch first, so M2 starts from a reviewed baseline.

- M2 is contract-additive and local-only: no provider calls are needed, because the tests use `FakeRetrieval`.
- The parent-immutability invariant is already covered.
- The target behavior is pinned by the strict-xfail tests.

The QA-branch security defects (URL userinfo) should be scheduled before any public deployment (M10). They don't block M2.

---

## 10. Follow-up: work done after the audit (2026-11-20)

Everything below is offline and local: no provider keys, no billable call. Browser tests ran against a throwaway copy of `exploration/data/exploration.sqlite`.

**M2 — implemented (contract 1.1.0, additive)**

- `create_branch` keeps the root question for every intervention. It stores `root_question`, `parent_question`, `objective_grounded` and `lifecycle="saved"`, with `status="created"`.
- A challenge needs an attached claim or a grounded objective. Otherwise the API returns 422.
- `planner.branch_query` builds the first branch query from the claim text. A vague objective is never sent alone.
- A legacy ungrounded challenge stops with `no_useful_actions` and runs no search.
- `step()` records `lifecycle` (`saved`, `researching`, `stopped`, `completed` or `failed`). A failed step records `last_error` and no results.
- Trace and list expose `root_question` and `lifecycle`. Legacy rows resolve the root question by walking the parent lineage.
- Frontend:
  - shows the root question, flags legacy overwrites, and drives badges from `lifecycle`
  - the composer refuses an ungrounded challenge, using the same rule as the backend
- `test_lantern_trace.py` no longer asserts the overwrite. `shared/evidence.schema.json` and `example_payload.json` are regenerated; they were already stale.

**M3 (non-billable parts)**

- Live "New investigation" saves a question and budget only.
- Every write sends `Idempotency-Key`; the backend stores the result and replays it, and a different body with the same key returns 409.
- At most one step runs per investigation (a concurrent step returns 409).
- A billable step asks for confirmation, and recorded events are polled while it runs.

**M4:** new searches record `round` and `planned_from`, and the adapter links a search to the question that prompted it.

**M5:** Live Findings view. Claims are grouped without losing record IDs. Exact-quote, semantic-only and independent-origin support are shown separately, and unknown origin is never counted as independent. The outcome is labelled partial unless the controller judged the evidence sufficient.

**M6:** Live parent↔child comparison of stored records. A question missing from the child is reported as "dropped or answered: the record does not say which".

**M8:** Live Knowledge view.
- Every node shows its basis.
- Corrections are explicit user assertions: they persist, survive a restart, and the latest one per subject wins.
- Retrieved sources stay "encountered".
- "Confirmed by you" appears only for your own assertions.

**M0:** CI runs offline pytest (3 key-dependent tests deselected), a contract-file freshness check, `tsc`, `vitest` and `build`. The environment-specific Streamlit test now skips.

**M9 (partial):**
- The header wraps instead of collapsing.
- New screens use ≥ 12 px text and visible focus.
- The "read-only" labels were removed, since the app now writes locally.

**Tests now**

| Suite | Result |
|---|---|
| Backend | 144 passed, 1 skipped, 3 failed (the provider-key tests, also failing on `origin/main`) |
| vitest | 94 / 94 |
| Playwright | 12 / 12, passing twice on the same DB |
| `tsc` / build | clean |

**Not done, because it needs your authorization or a decision**
- Commit, push and PR.
- Any live (billable) research run, which M2–M6 live acceptance and M10 evaluation depend on.
- Deployment and authentication (M11).

**Later additions**
- **M10 security:** URL userinfo (`user:password@`) is stripped in `focus.canonical_url` and in answer citations (`strip_userinfo`). The two QA-ledger tests are ported to `focus/test_url_userinfo.py`. Exploration's `normalize_url` was already safe and is now tested.
- **M4:** frontend tests cover replay determinism and that only persisted checkpoints are offered as fork points.
- **M9:** 244 CSS rules outside the zoomable canvas were raised from 7–9.5 px to 10–10.5 px. All 12 browser tests still pass.

Final: backend 147 passed, 3 failed (provider keys); vitest 96/96; Playwright 12/12; `tsc` and build clean.

**Follow-up branch `frontend/qa-and-m7-followup` (local, not pushed)**
- **QA ledger:** 89 pass, 3 skipped with stated reasons, 1 fails. The failure (`test_profile_value`) checks a recorded live demo file that predates the fix; it passes only after a re-recorded live run.
- **Behaviour changes worth reviewing:**
  - Retrieval failures now stop an investigation and record why.
  - Controller stops without a reason code are honoured.
  - A string `"false"` stop flag is parsed strictly.
  - When the API key is set, extraction runs the LLM even when a disclosed-fact pattern matched. That is **one more billable LLM call per such page in live runs**, within the budget.
  - Cited answers remove unsupplied markers and links, and remove sentences whose amount isn't in a cited quote.
- **M7:** per-passage coordinates are recorded in `policy_space_passages` and wired to the Inspector and the 3D view.
- **M6:** canvas layout is remembered per investigation.
- **M9:** keyboard pan, zoom, fit and Escape on the map.
- **Tests:** backend 148 passed, 1 skipped, 3 failed (provider keys); vitest 99/99; Playwright 15/15.

## 11. Resumed session (2026-11-20): CI repair, M7 verification, QA inventory

- **PR #4 CI** had failed in `backend › Contract files are up to date`. `shared/evidence.schema.json` had been generated with a local pydantic 2.9.2, but CI pins 2.14.3 (integer bounds, `additionalProperties`). The fix (`b6d8001`) regenerated the file with 2.14.3 in a clean venv and removed the three deselects:
  - `test_profile_live_pipeline_*` (2) use an in-process fake retrieval and assert zero network fetches; they failed only the orchestrator's `telem_configured()` gate, so the test now sets a placeholder `TELEM_API_KEY`.
  - `test_missing_api_key_uses_keyless_search_and_extract` needs no key.
  - The rerun was green: backend 151 passed (2 `integration` deselected), frontend tsc + vitest 98/98 + build.
- **Follow-up branch** `frontend/qa-and-m7-followup` was fast-forwarded onto `b6d8001`, and the previously uncommitted work was committed in two units: M7 (`cdbb6a5`) and QA fixes (`7dd79b3`).
- **Results on the follow-up branch** (no keys, empty `HOME`, pinned deps): backend 152 passed; QA ledger 90 pass / 1 fail / 2 skip; tsc clean; vitest 99/99; build clean; Playwright 15/15 against an isolated keyless API on :8010 serving a copy of `exploration/data/exploration.sqlite`.
- **Reconciling earlier reports.** "89 / 1 / 3" counted `test_fetch_lineage` as skipped (no telem-sdk in that interpreter); "3 key-dependent backend failures" were the three CI deselects above, and none of them was a QA-ledger test.
- **M8 slice** (`6500252`): a new investigation can copy the stored profile of the investigation it was started from. Backend 157 passed, vitest 103/103 (on the first full run, two UI tests hit the 5 s timeout while servers ran alongside; both passed in isolation and on a full rerun), Playwright 15/15 including frontier → saved question with `profile_from_investigation_id`, build clean.
