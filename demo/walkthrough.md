# Walkthrough

Measured on November 14, 2026. Counts below are the run recorded in `demo/evaluation.json`. One investigation is not a statistical result.

## Story C, offline

Question: "Do three articles independently substantiate a company's claim?"

`demo/run_demo.py` loads four local fictional documents. Network calls: 0. The B3 run found one shared origin, `LF-PR-2026-031`, with one original announcement and three derivatives. It marked the `$480 million` Series D sentence as contradicted and left the `$400 million` sentences supported. Stop reason: `unresolved_uncertainty`. Decision source: `fallback`, because the convergence endpoint was not running. B0 read the same corpus and did not classify the shared origin or the contradiction.

## Story A, live Telem

Question stored unchanged: "How do NVIDIA's investments, GPU infrastructure customers, and AI capacity expansion reinforce one another?"

The search query sent to Telem was `NVIDIA CoreWeave investment AI factories capacity 2026`. Providers: brave and tavily. This run made 2 searches and 4 provider calls, and Telem returned a session id plus two interaction ids. Fetch calls were served from the local fetch cache written by earlier live Telem fetches in the same session, so `urls_fetched` on this run is 0. Resume after the run reported `network_fetches: 0`.

Supported edges, each tied to an exact substring of a stored page:

- NVIDIA invested_in CoreWeave
- NVIDIA invested_amount $2 billion
- NVIDIA planned_capacity 5GW
- CoreWeave planned_capacity 1 GW

Nine supported rows are stored because more than one page contains the investment sentence. The demand-side question stayed open: "What downstream customer demand or product revenue is tied to the NVIDIA CoreWeave capacity expansion?" The follow-up search used that question. Stop reason: `unresolved_uncertainty`. No causal demand conclusion was stored.

Decision source: `fallback`. The convergence endpoint at `http://127.0.0.1:8000/api/convergence/evaluate` raised `RemoteProtocolError`.

The local LLM (`llama3.1:latest` on localhost) was called 6 times and timed out on page excerpts. The supported edges above came from exact-substring checks on the fetched pages, not from model JSON. `llm_tokens` and `cost_usd` were not reported by the APIs.
