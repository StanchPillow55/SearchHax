# Context Frontier — SearchHack prototype

An intent-anchored source selection engine with novelty control. **This does not verify truth or claim independence**; `consider` means *candidate for use*, not *fact established*.

## Run

```bash
python -m unittest -v test_focus_attention.py
pip install -r requirements.txt
streamlit run app.py
```

Start in `Demo passages` mode. The default lexical scorer requires only Python standard library and is fully testable offline. Check `Use semantic embeddings` to enable real sentence-transformer similarity; first run downloads the model. The fixed intent never drifts even if the candidate set changes.

For live retrieval, set `TAVILY_API_KEY` and/or `TELEM_API_KEY` environment variables. For Telem, `TELEM_SEARCH_URL` can override the default endpoint if your account uses a different API endpoint. **Live Telem and Tavily API contracts have not been exercised here**; check the current provider documentation and update the adapter if a response schema differs. Telem routing may already return Tavily results; choosing `Both` can result in duplicate paid searches.

## What is implemented

- URL deduplication, tracking query param removal, cross-batch seen key tracking
- Sequential novelty scoring across a batch and across multiple batches
- Optional embedding model; otherwise lexical Jaccard fallback
- Original-intent relevance and separate unresolved-question alignment
- Conservative separation of candidate evidence from verification queue
- Exploration budget and novelty threshold moving monotonically with slider
- Compact evidence packet from `consider` candidates only
- Stagnation and maximum-search-call stopping signals
- Optional Telem and Tavily search adapters, small Streamlit interface
- Tests for duplicate sources, semantic similarity, policy, and stopping

## Remaining production work

1. Integrate and validate actual API contracts, billing, and quotas.
2. Add targeted verification queries and record their results separately; **no automatic verification is performed**.
3. Add claim extraction, source lineage, and independent corroboration rather than treating provider overlap as corroboration.
4. Add token and cost telemetry; benchmark against top-K retrieval on labeled questions.
5. Calibrate semantic thresholds using real embeddings. Lexical thresholds are not transferable to embedding similarity.
6. Keep retrieved text untrusted (never treat it as agent instructions); implement rate limiting and retries.
7. The `should_stop` policy provides simple budget/stagnation safeguards, **not** genuine evidence sufficiency or expected information gain.

## Core design cautions

Novelty is not correctness. Source quality is only an uncalibrated prior supplied by the caller. Semantic similarity is clipped to [0,1] for this heuristic, and outliers with weak original-intent similarity can be missed. Archiving due to exploration budget means *deferred*, not disproven. Retrieval snippets may be insufficient for final fact checking.

### Extra entrypoints

- `python benchmark.py` shows a deterministic offline example with a **word-count proxy**, not actual model tokens.
- `research_loop.py` includes a max-call bounded discovery loop (`run_research(model, retrieve)`) that generates targeted search queries from unusual evidence. It does not independently verify the claims returned.
- The interactive 3D context space uses intent alignment, novelty, and unresolved-question alignment in every mode, including semantic embeddings. Embeddings can change those scores. They do not replace the axes with PCA. The chart is drawn by `context_space.py` for both the standalone app and the FrontierGraph evidence space.
- Optional cited-answer generation uses `answer_composer.py`; set `OPENAI_API_KEY` and enable the answer checkbox in the app. Archived sources are excluded and unknown citation markers are rejected.
- Gemini is also supported: set `GEMINI_API_KEY`, choose `Gemini` (or `Auto`) in the app, and optionally override `GEMINI_MODEL`.
- Local OpenAI-compatible servers are supported: set `LOCAL_BASE_URL` and `LOCAL_MODEL`, then choose `Local`. Ollama defaults to `http://localhost:11434/v1`.
