# FrontierGraph exploration

Exploration acquires evidence, builds a provenance graph, proposes one follow-up, and persists checkpoints. Attention scores rank passages for retrieval. They are not factual confidence. Convergence owns intent alignment, novelty, and the stopping policy. If `POST /api/convergence/evaluate` is down, exploration uses a labeled fallback and does not pretend the controller answered.

## Setup

```bash
python3.12 -m venv exploration/.venv
exploration/.venv/bin/pip install -r exploration/requirements.txt
cp .env.example .env
```

`.env` is gitignored. Required for a live run: `TELEM_API_KEY`. Extraction uses an OpenAI-compatible endpoint (`LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL`). `TAVILY_API_KEY` is used only when a Telem fetch returns an empty page.

The Telem client defaults to `https://router.telem.ai`.

## Run

Offline provenance demo, no network:

```bash
exploration/.venv/bin/python -m exploration.cli story-c
```

API:

```bash
exploration/.venv/bin/uvicorn exploration.backend.main:app --reload
```

`POST /api/exploration/fixtures/story-c` runs the synthetic three-article corpus.

Live Story A plus the Story C baseline metrics:

```bash
exploration/.venv/bin/python demo/run_demo.py --live
```

That writes `demo/evaluation.json` from the run that just finished. Counts in that file are measured. One investigation is not a statistical result.

## Tests

```bash
exploration/.venv/bin/pytest exploration/tests/test_exploration.py
exploration/.venv/bin/pytest exploration/tests/test_telem_live.py -m integration
```

The integration test skips when `TELEM_API_KEY` is missing.

## Caps

The backend refuses more than 2 searches, 5 fetched URLs, 5 URLs in one fetch, and 10 LLM calls, including when a controller asks for more.
