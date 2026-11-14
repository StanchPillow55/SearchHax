# Walkthrough

Measured on November 14, 2026. Counts below are the run recorded in `demo/evaluation.json`. One investigation is not a statistical result.

## Story C, offline

Question: "Do three articles independently substantiate a company's claim?"

`demo/run_demo.py` loads four local fictional documents. Network calls: 0. The B3 run found one shared origin, `LF-PR-2026-031`, with one original announcement and three derivatives. It marked the `$480 million` Series D sentence as contradicted and left the `$400 million` sentences supported. Stop reason: `unresolved_uncertainty`. Decision source: `fallback`, because the convergence endpoint was not running. B0 read the same corpus and did not classify the shared origin or the contradiction.

## Story A, live Telem

Question stored unchanged: "How do NVIDIA's investments, GPU infrastructure customers, and AI capacity expansion reinforce one another?"

The search query sent to Telem was `NVIDIA CoreWeave investment AI factories capacity 2026`. Providers: brave and tavily. Investigation `inv_8e46a18764e64eb0` started with an empty fetch cache. It made 2 searches, 4 provider calls, and fetched 5 URLs. Telem returned a session id and two interaction ids. Resume afterwards reported `network_fetches: 0`.

Supported edges are exact substrings of the stored pages, three copies of each because three pages contain the same sentence:

- NVIDIA invested_in CoreWeave
- NVIDIA invested_amount $2 billion

The demand-side question stayed open: "What downstream customer demand or product revenue is tied to the NVIDIA CoreWeave capacity expansion?" The follow-up search used that question. Stop reason: `unresolved_uncertainty`. No causal demand conclusion was stored.

Decision source: `fallback`. The convergence endpoint at `http://127.0.0.1:8000/api/convergence/evaluate` raised `RemoteProtocolError`.

The local LLM was called twice on pages that did not contain that investment sentence. The supported edges came from the exact sentence `NVIDIA has invested $2 billion in CoreWeave`, not from model JSON. `llm_tokens` and `cost_usd` were not reported.

## Profile demo, offline

The profile demo uses what the static profile already contains. Interests are AI systems, GPUs, data-center capacity, semiconductor, and the open interest advanced packaging. Known claims are profile priors: NVIDIA invested in CoreWeave, and capacity expansion is under investigation. Ceramics are not a listed interest.

`exploration/.venv/bin/python -m exploration.cli profile` reads three local documents and does not search. On this fixed corpus, ordinary query ranking (B0) orders the LLM benchmark page, then the ceramic packaging page, then the smartphone page. Knowledge-value ranking (B3) orders the ceramic packaging page first. Those are different passages. The surfaced bridge quotes `Using a ceramic substrate leads to less package warpage for advanced packaging of advanced chips.` The reason names the prior interest advanced packaging. Network calls: 0.

Iterative search itself is not the claim. This is one fixed corpus. It is not a claim about Tavily `/research` or a general LLM, and it is not proof that FrontierGraph outperforms an LLM with equivalent memory.
