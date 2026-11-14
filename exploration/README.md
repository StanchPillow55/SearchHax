# FrontierGraph exploration

Evidence-graph investigation service for SearchHax. It searches with Telem, ranks passages with a deterministic attention heuristic, verifies quotations against stored document text, and asks the convergence controller which follow-up to run.

Attention scores are retrieval priority. They are not factual confidence.

The convergence policy (intent alignment, novelty, redundancy, include/archive) lives in the other workstream. This package only POSTs to `CONVERGENCE_URL` and, if that endpoint is down, uses a labeled fallback. `decision_source` is `convergence` or `fallback`. A fallback decision is not a convergence decision.

## Setup

```bash
python3.12 -m venv exploration/.venv
exploration/.venv/bin/pip install -r exploration/requirements.txt
cp .env.example .env
```

Fill `.env` locally. Do not commit it.

`TELEM_BASE_URL` defaults to `https://router.telem.ai` when unset. Set it to `https://hack.telem.ai/api` if the event router should be used instead.

Hard caps, enforced in the backend regardless of controller instructions:

- 2 search operations per investigation
- 5 fetched URLs, and at most 5 URLs in one fetch call
- 10 LLM calls

Default Telem search uses providers `brave` and `tavily`, tier `default`, and 3 results per provider.

## Run

From the repository root:

```bash
exploration/.venv/bin/pytest
exploration/.venv/bin/python demo/run_demo.py
exploration/.venv/bin/python -m exploration.cli --db exploration/data/exploration.sqlite story-c
exploration/.venv/bin/uvicorn exploration.backend.main:app --host 127.0.0.1 --port 8080
```

`DRY_RUN=1` replays cached provider responses and `exploration/fixtures/replay/synthetic_search.json`. It does not open a network connection.

Story C is fully local:

```bash
curl -X POST http://127.0.0.1:8080/api/exploration/fixtures/story-c
```

## Tests

`exploration/.venv/bin/pytest` runs the deterministic suite. `test_telem_live_smoke` is marked `integration` and is skipped when `TELEM_API_KEY` is missing.

## What this package does not do

- No React UI
- No convergence scoring policy
- No Story B or Story D runner
- No claim that live NVIDIA relationships were extracted unless Telem and an LLM key were actually configured
