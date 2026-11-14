# Implementation status

Milestone: live Story A plus offline Story C, after the grounded-quote fix.

Implementation checkpoint: `c81ea8e` on `feat/exploration`. The native-schema benchmark did not change retrieval, grounding, or follow-up code. Unit tests after that benchmark: `exploration/.venv/bin/pytest -m "not integration"` — 31 passed, 2 integration tests deselected.

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

The Story A pipeline is unchanged from `c81ea8e`. Extraction still uses the OpenAI-compatible client at `{LLM_BASE_URL}/chat/completions` with a 12 second timeout, `max_tokens` 300, and `response_format` json_object. Supported Story A edges remain the exact sentence `NVIDIA has invested $2 billion in CoreWeave`. Failed model output is not turned into supported claims.

Ollama 0.40.16 is on `127.0.0.1:11434`. Native `POST /api/chat` benchmarks used a JSON schema, temperature 0, and `num_predict` 220, on the four Story C fixtures plus one short sentence. Timeout for the benchmark was 90 seconds. Neither model timed out. `ollama ps` showed 100% GPU for both (`qwen2.5:3b` on llamacpp, `qwen3.5:4b` on mlx), so the slow generations are not CPU offload.

`qwen2.5:3b`, schema required an exact quote. Cold load of the first passage was 12.654 seconds. Warm Story C generation was 0.670–0.711 seconds and returned 7 tokens, an empty `relationships` list. Zero of the four Story C amounts became supported relationships. The short sentence produced one supported relationship. Full rows are in `demo/llm_bench_qwen25_3b.json`.

`qwen3.5:4b` with `think` false. Warm generation was 18.233–32.729 seconds and 137–216 output tokens, which is past the 12 second client timeout. Grounded supported rows contained `$400 million` for the original and Northline passages and `$480 million` for VoltStreet. Harbor's `$400 million` row was `insufficient` after quote grounding; two other Harbor rows were supported. Other passages also emitted rows that grounding marked `insufficient`. Full rows are in `demo/llm_bench_qwen35_4b.json`.

Neither model is wired into extraction. Local LLM extraction stays experimental. A hosted open-weight endpoint would be the next place to look for schema extraction that finishes inside the demo budget. This machine is already offloading both models to the GPU.

## QA

`qa/tests` from `qa/exploration-verification` was run against this tree and was not added to the branch. Result: 15 passed, 2 failed.

- `test_duplicate_controller_query_is_not_executed`: a controller action that repeats the first query is searched again.
- `test_unresolved_gap_changes_which_page_is_fetched`: follow-up fetch rank uses the investigation question, so a snippet that overlaps the question outranks the unresolved-gap snippet.

Those two checks were left as they are so the `c81ea8e` follow-up behavior stays in place.

## Known limitations

- Convergence was not running. The labeled fallback selected the follow-up.
- Local schema extraction does not yet add its own grounded quotes inside the 12 second client timeout. Supported Story A edges are the exact sentence above, not model JSON.
- The same sentence is stored once per source page, so 6 supported rows are 2 facts on 3 pages.
- No React UI. The CLI and HTTP API are the exploration surface.

## Still open

- A local or hosted model that returns exact quotes before the client timeout without inventing supported claims.
- A live response from `POST /api/convergence/evaluate`.
- Human step: keep `TELEM_API_KEY`, `TAVILY_API_KEY`, and `LLM_*` in the gitignored `.env`. Do not commit it.

## Credentials

Present and used: Telem, Tavily, and a local OpenAI-compatible LLM. Values are not recorded here.
