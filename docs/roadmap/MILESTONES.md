# SearchHax V1 — milestone tracker

Status is set from **observed evidence only**: a test run, a screenshot or a persisted record. Last update: 2026-11-20 (`docs/audit/M0-M1-audit.md`, section 10).

Status legend:
- ✅ exit criteria verified
- 🟡 partial
- 🔲 not started
- ⛔ needs your authorization (billable or outward-facing)

| # | Milestone | Status | Evidence / what is left |
|---|---|---|---|
| M0 | Integration baseline | 🟡 | Linear +8 over `origin/main`, no secrets, clean trial merge with QA. CI added (`.github/workflows/ci.yml`). **Left:** commit, push and PR (⛔ needs your go-ahead). |
| M1 | Real-data React reader | ✅ | 10/10 checks on the live API; screenshots |
| M2 | Grounded branching and lifecycle | ✅ (offline) | Root question kept, objective separate, ungrounded challenge → 422, claim-grounded challenge query, `lifecycle`, legacy rows resolved. Backend + vitest + e2e. **Not observed:** a real (billable) child research run ⛔ |
| M3 | Live research execution | 🟡 | New Investigation (local), idempotency keys on every write, one step at a time per investigation (409), billable confirm dialog, polling of recorded events during a step. **Left:** an authorized live run ⛔ |
| M4 | Truthful trace and playback | ✅ (new runs) | Playback, snapshots and compare on real data. New searches record `round` and `planned_from` (prompting question/action), and the adapter uses them. Replay determinism and "only persisted checkpoints are forkable" are tested. **Left:** older runs keep derived rounds (their events predate the fields). |
| M5 | Evidence-grounded findings | 🟡 | Live Findings: claims grouped without erasing records, and exact-quote vs semantic-only vs independent origins kept apart. Unknown origin is never counted as independent. Partial outcomes are labelled. A stored cited answer is shown separately. **Left:** a gated "generate cited summary" button (billable ⛔); QA-ledger correctness defects. |
| M6 | Lineage and comparison | 🟡 | Constellation from real `/branches`; live parent↔child compare (claims, sources, questions, disagreements, stop decisions); grandchild keeps the root question. **Left:** persist canvas position. |
| M7 | Real 3D Focus space | 🟡 | Recorded `policy_space`, synced with the trace, honest empty state. **Left:** per-passage coordinates (backend), branch overlay. |
| M8 | Personal knowledge | ✅ (local) | Live Knowledge view with the basis of every node. Correction → persists across restart → latest wins. Encountered never becomes known. Frontier pre-fills a new question. **Left:** passing the profile to the new investigation for profile-aware ranking. |
| M9 | UX and accessibility | 🟡 | New screens use ≥ 12 px body text and focus outlines. The header wraps instead of collapsing; responsive at < 900 px. Sub-10px text outside the zoomable canvas was raised: 244 rules now have a 10–10.5 px minimum. **Left:** a keyboard audit of the canvas. |
| M10 | QA, security, evaluation | 🟡 | URL credentials are stripped from source keys and citations; 2 QA ledger tests are ported and passing (`focus/test_url_userinfo.py`). 57 other recorded QA defects are still open. No auth. B0/B1/B2 evaluation requires live runs ⛔ |
| M11 | Deploy and release | ⛔ | Hosting, secrets and authentication are outward-facing decisions for you |

## V1 release acceptance (4 / 13 observed; locally, offline)

- [x] Submit a new research question through React and create a real backend investigation (saved, not run)
- [ ] Watch real search, extraction, evaluation and convergence activity ⛔ billable
- [ ] Receive grounded findings with citations and explicit uncertainty — findings view done; needs a new live run ⛔
- [x] Replay and inspect the sources behind each recorded decision (persisted runs)
- [x] Return to an eligible intermediate checkpoint
- [x] Challenge a claim and fork without losing the original question (saved child; e2e)
- [ ] Run child research using the attached claim and checkpoint ⛔ billable (planning verified offline)
- [ ] Compare parent and child findings, evidence and unresolved questions — done for a recorded child; needs a fresh researched child ⛔
- [ ] Select a passage in the Lantern Map and find the same point in 3D — works at document level; per-passage needs backend (M7)
- [ ] Inspect and correct a knowledge assertion; see it persisted — verified (e2e + restart test); left open until a deployed run
- [ ] Restart without losing investigations, branches or checkpoints — verified locally on SQLite; needs the deployed check
- [ ] Pass the offline, integration, browser, security and budget tests — offline and browser pass; security and integration open
- [ ] Use the deployed app without local developer tools ⛔
