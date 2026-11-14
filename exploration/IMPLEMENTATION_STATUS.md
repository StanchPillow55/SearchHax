# Implementation status

Milestone: live Story A plus offline Story C, after the grounded-quote fix.

Commit: `7f16d8f` on `feat/exploration`. Unit tests: 15 passed in `exploration/tests/test_exploration.py`.

## Verification level

- Implemented and unit-tested: URL normalization, provider dedupe, attention bounds, quote rejection, relationship schema, provenance classification, budget caps, Story C contradiction, checkpoint reload, convergence fallback, disclosed NVIDIA/CoreWeave quote extraction.
- Integration-tested: one live Telem search returned CoreWeave/NVIDIA titles with a session id and an interaction id (`exploration/tests/test_telem_live.py`, plus the Story A run below).
- End-to-end: `exploration/.venv/bin/python -u demo/run_demo.py --live` completed. Story C and Story A figures are in `demo/evaluation.json`.

Unit tests last run: `exploration/.venv/bin/pytest exploration/tests/test_exploration.py` — 15 passed.

## This run

Story C B3: shared origin `LF-PR-2026-031`, 1 contradiction, 0 network calls, stop `unresolved_uncertainty`.

Story A `inv_2459ddc7705c45f0`: 2 Telem searches, 4 provider calls, 9 supported relationships, 1 follow-up, decision source `fallback` (`RemoteProtocolError` from the convergence URL), stop `unresolved_uncertainty`, resume network fetches 0. Page bodies on this run came from the fetch cache. `urls_fetched` is 0 for that reason. `cost_usd` and `llm_tokens` are null.

## Files

- `shared/contracts.py`, `shared/evidence.schema.json`, `shared/example_payload.json`
- `exploration/backend/` retrieval, attention, extraction, verification, graph, database, checkpoints, planner, orchestrator, baseline, API
- `exploration/cli.py`, `exploration/fixtures/story_c/`, `exploration/tests/`
- `demo/run_demo.py`, `demo/evaluation.json`, `demo/walkthrough.md`
- `.env.example`

## Known limitations

- Convergence was not running. The labeled fallback selected the follow-up.
- Local `llama3.1:latest` timed out on page excerpts. Supported Story A edges are exact substrings of fetched pages, not LLM JSON.
- The same investment sentence is stored once per source page, so the supported count is not a count of distinct facts.
- `urls_fetched` does not increase when a URL is already in the fetch cache.
- No React UI. The CLI and HTTP API are the exploration surface.

## Still open from the original goal

- A cold-cache Story A in which `urls_fetched` is greater than 0 on the same run as the grounded edges.
- An LLM extraction that returns before timeout and adds grounded quotes of its own.
- A live response from `POST /api/convergence/evaluate`.
- Human step: keep `TELEM_API_KEY`, `TAVILY_API_KEY`, and `LLM_*` in the gitignored `.env`. Do not commit it.

## Credentials

Present and used: Telem, Tavily, and a local OpenAI-compatible LLM. Values are not recorded here.
