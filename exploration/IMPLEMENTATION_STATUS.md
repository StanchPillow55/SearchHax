# Implementation status

Milestone: live Story A plus offline Story C, after the grounded-quote fix.

Implementation checkpoint: `c81ea8e` on `feat/exploration` for retrieval, grounding, and follow-up. Local Ollama chat calls are not sent unless `LLM_FORCE_LOCAL=1`. Unit tests after that change: `exploration/.venv/bin/pytest -m "not integration"` — 32 passed, 2 integration tests deselected.

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

## Local LLM benchmark

Supported Story A edges remain the exact sentence `NVIDIA has invested $2 billion in CoreWeave`. The extraction client still has a 12 second timeout, `max_tokens` 300, and `response_format` json_object. A base URL on localhost, `127.0.0.1`, or `::1` now raises `LocalExtractionUnavailable` before the HTTP call unless `LLM_FORCE_LOCAL=1`. Disclosed-fact and Story C extractors are unchanged. Failed model output is not turned into supported claims.

Ollama 0.40.16 is on `127.0.0.1:11434`. The configured model is `qwen2.5:7b-instruct-q4_K_M`. One native `POST /api/chat` pass over `original.md`, outside the app, finished in 51.481 seconds: load 4.594, prompt evaluation 2.272, generation 44.571, 206 prompt tokens, 156 output tokens. Schema validation passed. The `$400 million` row was `insufficient`. `ollama ps` reported 100% GPU. The ReadTimeout is that generation, on GPU, running past the 12 second client deadline.

Native schema benchmarks used temperature 0, `num_predict` 220, and a 90 second cap on the four Story C fixtures plus one short sentence. No run hit that cap.

`qwen2.5:3b`. Cold load of the first passage was 12.654 seconds. Warm Story C generation was 0.670–0.711 seconds and returned 7 tokens, an empty `relationships` list. Zero of the four Story C amounts became supported relationships. The short sentence produced one supported relationship. Rows: `demo/llm_bench_qwen25_3b.json`.

`qwen3.5:4b` with `think` false, 100% GPU. Warm generation was 18.233–32.729 seconds and 137–216 output tokens. Grounded rows contained `$400 million` for the original and Northline passages and `$480 million` for VoltStreet. Harbor's `$400 million` row was `insufficient`. Rows: `demo/llm_bench_qwen35_4b.json`.

`llama3.2:latest` is the installed 3.2B Q4_K_M model, used in place of a second download. Warm generation on the press-release passages was 20.124–21.973 seconds. The original passage grounded its amount. Northline, Harbor, and the short sentence did not. VoltStreet returned invalid JSON (`JSONDecodeError`) on both passes. Rows: `demo/llm_bench_llama32_3b.json`.

Selected configuration: disclosed-fact and Story C extraction, with local Ollama left uncalled. A hosted OpenAI-compatible URL still uses `/chat/completions`. Local LLM extraction remains experimental.

## QA

`qa/tests` from `qa/exploration-verification` was run against this tree and was not added to the branch. Result: 17 passed.

A controller action that repeats a query already in search history is not searched again. Follow-up fetch ranking passes open question text into attention, so the gap term can outrank a snippet that only overlaps the original question. The first search still happens before any open question exists, which is the Story A fetch of five URLs.

## Known limitations

- Convergence was not running. The labeled fallback selected the follow-up.
- Local schema extraction does not add its own grounded quotes inside the 12 second client timeout. Those calls are not sent. Supported Story A edges are the exact sentence above.
- The same sentence is stored once per source page, so 6 supported rows are 2 facts on 3 pages.
- No React UI. The CLI and HTTP API are the exploration surface.

## Still open

- A local or hosted model that returns exact quotes before the client timeout without inventing supported claims.
- A live response from `POST /api/convergence/evaluate`.
- Human step: keep `TELEM_API_KEY`, `TAVILY_API_KEY`, and `LLM_*` in the gitignored `.env`. Do not commit it.

## Credentials

Present and used: Telem, Tavily, and a local OpenAI-compatible LLM. Values are not recorded here.
