# SearchHax V1 — milestone tracker

Status is set from **observed evidence only**: a test run, a screenshot or a persisted record. Last update: 2026-11-20, after the first authorized live session (`docs/audit/M0-M1-audit.md`, section 12).

Branches: PR #4 = `frontend/react-integration` (CI green at `b6d8001`). PR #5 = `frontend/qa-and-m7-followup`, stacked on #4, with everything since. Nothing is merged into `main`; merging is your decision.

**Overall: V1 is INCOMPLETE.** Live research, branching, findings, 3D and knowledge were demonstrated once in React (local, capped budget). Open: merging, a public or shared deployment (not authorized), evaluation beyond the recorded Story C/A baselines, and the defects below.

Status legend:
- ✅ exit criteria verified
- 🟡 partial
- 🔲 not started
- ⛔ needs your authorization (billable or outward-facing)

| # | Milestone | Status | Evidence / what is left |
|---|---|---|---|
| M0 | Integration baseline | 🟡 | PR #4 green (backend, frontend). PR #5 is stacked on it with the browser job added to CI. No secrets in git; worktrees intact. **Left:** your review and merge of #4 then #5 (⛔ your decision). |
| M1 | Real-data React reader | ✅ | 10/10 checks on the live API; screenshots |
| M2 | Grounded branching and lifecycle | ✅ (live, once) | Live 2026-11-20: a challenge child `inv_7647b6b549474dd2` was created from claim `clm_2d994c177a997b8f` with the vague objective "Is this true?". Its search was "independent evidence for or against: NVIDIA has invested $2 billion in CoreWeave". The root question was kept, the objective stored separately, the claim and source attached, the parent unchanged, and the lifecycle went saved → stopped. Offline: backend + vitest + e2e (seeded CI DB includes a legacy row). |
| M3 | Live research execution | ✅ (live, once; local) | Live root `inv_51b381d9c7d24e59` through React: save → billable confirm → step (1 search, 4 URLs, 4 LLM calls) → **Continue research** (`36370d6`, added after the live run showed no way to continue) → convergence stop `unresolved_uncertainty`. Fork & Investigate ran a child behind its in-page authorization (1/5/5 of a 1/5/6 budget). Budgets enforced server-side. **Open defect:** one extraction recorded `LLM extraction failed: JSONDecodeError`; the cause is unconfirmed (blocker now records the finish reason, `9caa669`). |
| M4 | Truthful trace and playback | ✅ (new runs) | Playback, snapshots and compare on real data. New searches record `round` and `planned_from` (prompting question/action), and the adapter uses them. Replay determinism and "only persisted checkpoints are forkable" are tested. **Left:** older runs keep derived rounds (their events predate the fields). |
| M5 | Evidence-grounded findings | ✅ (live, once) | Live Findings: "PARTIAL / NOT VERIFIED", 6 records grouped as 1 claim ("repetition is not extra support"), 6 exact-quote, 0 independent origins, 3 of unknown origin, the recorded stop rationale. Repeated open questions are now grouped (`9d06b18`). **Left:** the "generate cited summary" button (billable, not built). Source independence is mostly "unknown origin" on live pages, so independence is rarely established. |
| M6 | Lineage and comparison | ✅ (live, once) | Live parent↔child compare: 1 claim unchanged, 4 shared + 5 new sources, a new claim-grounded open question, and the stop reasons of both. Constellation, grandchild root question, and canvas restore covered offline (e2e). |
| M7 | Real 3D Focus space | ✅ (live, once) | Live child: passage → its own point ("C2 · passages · 4 recorded points", investigate = orange) → "Show in investigation trace" → `evidence_spans · span_fbbf324e71fa7966`. Passage rows carry their own investigation id (parent and child points differ for the same span ids). Offline requirements 1–10 as before (`cdbb6a5`). **Not done (P3):** a parent+child overlay. |
| M8 | Personal knowledge | ✅ (live, once) | Live profile run `inv_31231a071b084408`: 2 known priors, 5 interests, 1 frontier, 4 encountered sources. Marking an encountered source "I know this" persisted across a reload and a backend restart as "confirmed by you", and the source stayed encountered. A frontier carries the stored profile into a new question (`6500252`). **Gap (P2):** corrections are not yet ranking inputs. |
| M9 | UX and accessibility | ✅ (local) | Text below 10px outside the canvas raised (244 rules); header wraps; map supports keyboard pan, zoom, fit and Escape, and nodes are focusable buttons with visible focus (e2e). |
| M10 | QA, security, evaluation | 🟡 | QA ledger: 91 pass / 0 fail / 2 skipped pending product decisions (Q13, Q17). Q25 closed by the live re-recording (`c43df7c`). CI: backend, frontend, and a **browser job on an offline-seeded DB** (`4aebd73`; 15/15 locally). Security: URL userinfo stripped, idempotency, single-flight, billable gate, basic auth for deployment, CORS wildcard refused. **Left:** accounts and authorization (none), B1/B2 evaluation (only the B0/B3 Story C and Story A baselines are recorded), the live JSONDecodeError. |
| M11 | Deploy and release | 🟡 | Container deployment (`a51cadd`, `docs/deploy/DEPLOY.md`): both images build, health checks pass, state survives compose down/up on the volume, basic auth verified (401/200), bound to 127.0.0.1. **Not done:** any public or shared deployment, TLS, real migrations (none needed yet), and a research-to-branch run *inside* the containers (the live run used the dev servers). ⛔ needs a host and authorization. |

## V1 release acceptance (11 / 13 observed; local, live once on 2026-11-20)

- [x] Submit a new research question through React and create a real backend investigation
- [x] Watch real search, extraction, evaluation and convergence activity (live root, 2 steps)
- [x] Receive grounded findings with citations and explicit uncertainty (live Findings: partial / not verified)
- [x] Replay and inspect the sources behind each recorded decision
- [x] Return to an eligible intermediate checkpoint (live C1: persisted, resumable)
- [x] Challenge a claim and fork without losing the original question (live, "Is this true?")
- [x] Run child research using the attached claim and checkpoint (live Fork & Investigate)
- [x] Compare parent and child findings, evidence and unresolved questions (live)
- [x] Select a passage in the Lantern Map and find the same point in 3D (live child)
- [x] Inspect and correct a knowledge assertion; see it persisted (live, across reload and restart)
- [x] Restart without losing investigations, branches or checkpoints (live DB: identical snapshot after a backend restart; container volume after compose down/up)
- [ ] Pass the offline, integration, browser, security and budget tests: offline, browser and budget pass; there is no account/authorization model to test
- [ ] Use the deployed app without local developer tools: container verified locally only ⛔ host not chosen

## Handoff: next actionable tasks

1. Review and merge PR #4, then PR #5 (yours).
2. Diagnose the live `JSONDecodeError`: run one more capped live step, which now records the finish reason. If it is `length`, raise or adapt `max_tokens` for Anthropic in `exploration/backend/llm.py`.
3. Make knowledge corrections ranking inputs (M8 P2): feed confirmed `known` assertions into `knowledge_value` as known claims.
4. Decide Q13 and Q17 (`qa/tests/README.md`).
5. Choose a host for M11 and authorize it; then repeat the research-to-branch flow inside the containers with keys and `VITE_ALLOW_BILLABLE_RESEARCH=true`.
