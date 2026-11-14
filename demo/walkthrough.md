# FrontierGraph walkthrough

Measured on November 14, 2026. Each configuration is one investigation, not a statistical result. Token and dollar amounts are null wherever the API did not return them.

## Live Story A

The stored question is unchanged: "How do NVIDIA's investments, GPU infrastructure customers, and AI capacity expansion reinforce one another?"

What actually ran, against an empty fetch cache:

- 1 Telem search, providers brave and tavily (2 provider calls)
- 1 Telem fetch of 5 URLs
- 1 LLM call, which failed with `ReadTimeout`
- 0 relationships stored

The investigation stopped with `unresolved_uncertainty` and `decision_source: fallback`. The fallback did not invent NVIDIA relationships after extraction failed. Latency for that run was 121579 ms. No usage tokens or cost were returned.

Resume loaded the five cached documents and reported `network_fetches: 0`.

A separate `pytest -m integration` run passed two live Telem searches. Earlier in the session, before the API key was available, a direct SDK call returned `AuthError` with HTTP 401 and no results.

## Story C, offline

Question: "Do three articles independently substantiate a company's claim?"

The corpus is four fictional files. No Telem, Tavily, or LLM call is made.

The original Lumenarc Dynamics release and three derivative articles share wire ID `LF-PR-2026-031`. One document is the original. Three cite it. They are not treated as independent sources.

VoltStreet says the Series D was `$480 million`. The original announcement and the other two articles say `$400 million`. B3 stores the `$480 million` relationship as `contradicted`. The quotation is still an exact substring of the VoltStreet article: quotation validity is not semantic support.

The convergence endpoint was not running. The recorded decision source is `fallback`, not `convergence`. The fallback ran one local follow-up looking for a Series D amount that does not cite the wire. None exists in the corpus. Stop reason: `unresolved_uncertainty`.

Reload of the four stored versions made no network fetches.

B0, same corpus and the same deterministic extractor, one pass, no provenance graph and no follow-up:

- 21 supported relationships, 0 contradiction detections, 13 exact citations
- latency 39 ms

B3:

- 20 supported relationships, 1 contradicted relationship, 1 contradiction detection, 13 exact citations
- latency 35 ms
- 1 local follow-up counted as a search operation, 0 provider calls, 0 URLs fetched, 0 LLM calls

The extra supported relationship in B0 is the `$480 million` sentence, which is locally quoted and not checked against the original.
