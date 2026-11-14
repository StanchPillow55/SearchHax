# Implementation status

Milestone: live Story A plus offline Story C, after the grounded-quote fix.

Commit: recorded after this checkpoint. Unit tests: `exploration/.venv/bin/pytest -m "not integration"` — 31 passed, 2 integration tests deselected.

## Verification level

- Implemented and unit-tested: URL normalization, provider dedupe, attention bounds, quote rejection, relationship schema, provenance classification, budget caps, Story C contradiction, checkpoint reload, convergence fallback, disclosed NVIDIA/CoreWeave quote extraction.
- Integration-tested: one live Telem search returned CoreWeave/NVIDIA titles with a session id and an interaction id (`exploration/tests/test_telem_live.py`, plus the Story A run below).
- End-to-end: `exploration/.venv/bin/python -u demo/run_demo.py --live` completed. Story C and Story A figures are in `demo/evaluation.json`.

Unit tests last run: `exploration/.venv/bin/pytest exploration/tests/test_exploration.py` — 15 passed.

## This run

Story C B3: shared origin `LF-PR-2026-031`, 1 contradiction, 0 network calls, stop `unresolved_uncertainty`.

Story A `inv_8e46a18764e64eb0`, empty fetch cache: 2 Telem searches, 4 provider calls, 5 URLs fetched, 6 supported relationships (`invested_in` CoreWeave and `invested_amount` $2 billion, each on three pages), 1 follow-up, decision source `fallback` (`RemoteProtocolError`), stop `unresolved_uncertainty`, resume network fetches 0. `cost_usd` and `llm_tokens` are null.

## Files

- `shared/contracts.py`, `shared/evidence.schema.json`, `shared/example_payload.json`
- `exploration/backend/` retrieval, attention, extraction, verification, graph, database, checkpoints, planner, orchestrator, baseline, API
- `exploration/cli.py`, `exploration/fixtures/story_c/`, `exploration/tests/`
- `demo/run_demo.py`, `demo/evaluation.json`, `demo/walkthrough.md`
- `.env.example`

## Known limitations

- Convergence was not running. The labeled fallback selected the follow-up.
- Local `llama3.1:latest` did not return JSON for the two pages that lacked the investment sentence. Supported edges are the exact sentence `NVIDIA has invested $2 billion in CoreWeave`, not model JSON.
- The same sentence is stored once per source page, so 6 supported rows are 2 facts on 3 pages.
- No React UI. The CLI and HTTP API are the exploration surface.
- Convergence was not running, so the follow-up is the labeled fallback.

## Still open

- An LLM extraction that returns before timeout and adds its own grounded quotes.
- A live response from `POST /api/convergence/evaluate`.
- Human step: keep `TELEM_API_KEY`, `TAVILY_API_KEY`, and `LLM_*` in the gitignored `.env`. Do not commit it.

## Credentials

Present and used: Telem, Tavily, and a local OpenAI-compatible LLM. Values are not recorded here.
