# SearchHax V1 — milestone tracker

Status is set from **observed evidence only**: a test run, a screenshot or a persisted record. Last update: 2026-11-20, after PR #4 CI was fixed (`docs/audit/M0-M1-audit.md`, section 11).

Branches: PR #4 = `frontend/react-integration` (CI green at `b6d8001`). Work that is not yet in PR #4 sits on `frontend/qa-and-m7-followup`, which is stacked on PR #4 and is local until you approve a push. Rows marked *(follow-up)* depend on it.

Status legend:
- ✅ exit criteria verified
- 🟡 partial
- 🔲 not started
- ⛔ needs your authorization (billable or outward-facing)

| # | Milestone | Status | Evidence / what is left |
|---|---|---|---|
| M0 | Integration baseline | 🟡 | PR #4 is open, mergeable, and offline CI is green (backend 151 passed / 2 integration deselected; tsc, vitest 98/98, build). The CI failure was a stale schema generated with an unpinned local pydantic; it was regenerated with the pinned 2.14.3. The 3 "key-dependent" deselects were removed: 2 use a fake retrieval and only needed the Telem config gate satisfied, and 1 needs no key. **Left:** review and merge (⛔ your decision); push the follow-up branch. |
| M1 | Real-data React reader | ✅ | 10/10 checks on the live API; screenshots |
| M2 | Grounded branching and lifecycle | ✅ (offline) | Root question kept, objective separate, ungrounded challenge → 422, claim-grounded challenge query, `lifecycle`, legacy rows resolved. Backend + vitest + e2e. **Not observed:** a real (billable) child research run ⛔ |
| M3 | Live research execution | 🟡 | New Investigation (local), idempotency keys on every write, one step at a time per investigation (409), billable confirm dialog, polling of recorded events during a step. **Left:** an authorized live run ⛔ |
| M4 | Truthful trace and playback | ✅ (new runs) | Playback, snapshots and compare on real data. New searches record `round` and `planned_from` (prompting question/action), and the adapter uses them. Replay determinism and "only persisted checkpoints are forkable" are tested. **Left:** older runs keep derived rounds (their events predate the fields). |
| M5 | Evidence-grounded findings | 🟡 | Live Findings: claims grouped without erasing records, and exact-quote vs semantic-only vs independent origins kept apart. Unknown origin is never counted as independent. Partial outcomes are labelled. A stored cited answer is shown separately. **Left:** a gated "generate cited summary" button (billable ⛔); QA-ledger correctness defects. |
| M6 | Lineage and comparison | ✅ (local) | Constellation from real `/branches`; live parent↔child compare; grandchild keeps the root question; canvas layout remembered per investigation (this browser). **Not observed:** comparing a freshly researched child ⛔ |
| M7 | Real 3D Focus space | ✅ (new runs; follow-up `cdbb6a5`) | Verified against code and persisted records. (1) One point per stored span, scored from that span's text (backend test). (2) Rows carry investigation, branch, document and span ids; the adapter drops rows recorded for another investigation and says so (vitest). (3–5) Passage → own point → 3D → "Show in investigation trace" → same span (e2e on a fresh offline Story C record). (6) Points are keyed per checkpoint and per investigation trace. (7) Scores are computed only when a checkpoint is saved; branching leaves the parent's recorded points byte-identical (backend test). (8) No coordinates → explicit `ix-no-coords` block; a passage without its own point is labelled document-level. (9) Document `policy_space` is unchanged apart from a `granularity` tag (backend test). (10) A child's points carry the child's ids (backend test). **Not done (P3):** a parent+child overlay in one 3D view. Older runs have document-level points only. |
| M8 | Personal knowledge | ✅ (local; follow-up `6500252`) | Live Knowledge view with the basis of every node. A correction persists across restart and the latest wins. Encountered never becomes known. A frontier pre-fills a new question **and carries the source investigation's stored profile** (`profile_from_investigation_id`, contract 1.2.0; copied server-side, opt-out in the form; backend + vitest + e2e). **Not observed:** profile-aware ranking in a live step ⛔. User corrections are shown and stored, but are not yet inputs to knowledge-value ranking (P2 design gap). |
| M9 | UX and accessibility | ✅ (local) | Text below 10px outside the canvas raised (244 rules); header wraps; map supports keyboard pan, zoom, fit and Escape, and nodes are focusable buttons with visible focus (e2e). |
| M10 | QA, security, evaluation | 🟡 | QA ledger (`qa/tests/README.md` has the inventory): 39 open on PR #4 → 36 fixed on the follow-up (`7dd79b3`); 90 pass, 1 open (Q25: needs a re-recorded live demo ⛔), 2 skipped pending product decisions (Q13, Q17). URL credentials are stripped. **Left:** authentication; Playwright is not in CI (it needs a DB fixture); B0/B1/B2 evaluation and live re-recording need live runs ⛔ |
| M11 | Deploy and release | ⛔ | Hosting, secrets and authentication are outward-facing decisions for you |

## V1 release acceptance (5 / 13 observed; locally, offline)

- [x] Submit a new research question through React and create a real backend investigation (saved, not run)
- [ ] Watch real search, extraction, evaluation and convergence activity ⛔ billable
- [ ] Receive grounded findings with citations and explicit uncertainty — findings view done; needs a new live run ⛔
- [x] Replay and inspect the sources behind each recorded decision (persisted runs)
- [x] Return to an eligible intermediate checkpoint
- [x] Challenge a claim and fork without losing the original question (saved child; e2e)
- [ ] Run child research using the attached claim and checkpoint ⛔ billable (planning verified offline)
- [ ] Compare parent and child findings, evidence and unresolved questions — done for a recorded child; needs a fresh researched child ⛔
- [x] Select a passage in the Lantern Map and find the same point in 3D (new runs; follow-up branch; e2e)
- [ ] Inspect and correct a knowledge assertion; see it persisted — verified (e2e + restart test); left open until a deployed run
- [ ] Restart without losing investigations, branches or checkpoints — verified locally on SQLite; needs the deployed check
- [ ] Pass the offline, integration, browser, security and budget tests — offline and browser pass; security and integration open
- [ ] Use the deployed app without local developer tools ⛔
