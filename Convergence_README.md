**Yes. Using Telem AI and Tavily actually makes your convergence idea more interesting.** It gives you multiple search perspectives and the ability to control when the agent retrieves more information.

The core novelty algorithm doesn't need to change. What changes is the architecture around it.

I would build **a convergence controller that sits above Telem and Tavily**, rather than letting either search API make the final decision about which evidence the agent should consider.

## **1. How I would divide the responsibilities**

| Component               | Responsibility                                                                    |
| ----------------------- | --------------------------------------------------------------------------------- |
| Telem AI                | Retrieve results across multiple search providers and expose provider information |
| Tavily                  | Search targeted queries, obtain relevant content, and extract selected pages      |
| Your convergence engine | Measure intent alignment, context novelty, redundancy, and source value           |
| LLM                     | Verify unusual claims, generate follow-up queries, and synthesize answers         |
| 3D interface            | Visualize the evolving evidence space and novelty boundary                        |

Telem currently supports searching multiple providers through a unified API, including Tavily, Exa, and Brave. Its auto-routing mode can also select providers based on the topic.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://docs.telem.ai\&sz=32)

Telem+1



Tavily supports a two-stage workflow: search broadly, select relevant results, and then extract detailed content from the most promising URLs.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://help.tavily.com\&sz=32)

Tavily Help Center



That combination is well suited to your concept.

## **2. Revised architecture**

**Original research question**

Fixed intent anchor

Telem

Multi-provider discovery and routing

Tavily

Targeted search and detailed extraction

**Your convergence controller**

Original intent alignment

Novelty against known evidence

Source deduplication

Verification priority

Include

Investigate

Archive

**Compact evidence context**

LLM generates grounded answer

## **3. The biggest change: multi-provider convergence**

Previously, we discussed sources converging toward a context representation.

With Telem, you can observe an additional signal: **which search providers find which sources**.

For example, suppose you ask why electric vehicle demand is weakening.

Illustrative retrieval results

| Source | Provider       | Finding                                         |
| ------ | -------------- | ----------------------------------------------- |
| A      | Brave          | Price sensitivity                               |
| B      | Tavily         | Charging concerns                               |
| C      | Exa            | Financing conditions                            |
| D      | Exa            | Battery degradation and resale-value hypothesis |
| E      | Brave + Tavily | Price sensitivity                               |

Your engine might recognize that Source D is unusual relative to the current evidence but potentially relevant to the original question.

Instead of discarding it, it can send a targeted query to Tavily to investigate the battery-related hypothesis.

But be careful: appearing in multiple search providers does **not** mean a claim has independent corroboration. Both may have found the same webpage or copied reporting.

You should track both provider provenance and underlying source provenance.

## **4. Make the slider control exploration behavior**

Here's where I think your implementation can stand out.

## **Live convergence policy simulator**

Exploration / novelty

**50%**

Focused

Balanced

Exploratory

Maximum search calls

**6**

What happens to candidate evidence?

EV pricing and affordability

Novelty 12% · Intent 95%

Consider

Charging infrastructure

Novelty 31% · Intent 88%

Consider

Battery longevity and resale value

Novelty 70% · Intent 83%

Investigate

Unrelated battery chemistry discovery

Novelty 91% · Intent 19%

Archive

At this setting, the controller accepts candidate evidence with novelty up to approximately 55% for ordinary consideration. Higher-novelty, intent-relevant claims are routed to a verification queue. The 6-call limit caps further retrieval.

Illustrative scores and policy. Actual novelty thresholds must be calibrated against the selected embedding model and dataset.

In the implementation, the slider should determine how much the agent explores; it shouldn't directly determine whether something is true.

## **5. How I would use the APIs**

For your initial search, I would let Telem perform multi-provider discovery.

Its documented endpoint is:

```
import osimport requestsresponse = requests.post(    "https://router.telem.ai/v1/search",    headers={        "Authorization": f"Bearer {os.environ['TELEM_API_KEY']}",        "Content-Type": "application/json"    },    json={        "user_input": {            "query": "Why might EV demand decline?"        },        "search": {            "providers": {                "include": ["exa", "brave", "tavily"]            },            "num_results": 5,            "include_full_content": False        }    },    timeout=30)response.raise_for_status()data = response.json()
```

Those endpoint and request fields match Telem's documented API.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://docs.telem.ai\&sz=32)

Telem AI Docs+1



Notice that full-content retrieval is disabled.

That's intentional: **you don't want to fetch and embed every entire webpage before knowing whether it deserves attention.**

Instead, score the initial result snippets and extract only promising sources.

For follow-up searches, you can use Tavily directly:

```
from tavily import TavilyClientimport ostavily = TavilyClient(    api_key=os.environ["TAVILY_API_KEY"])results = tavily.search(    query=(        "evidence battery degradation concerns "        "affect electric vehicle purchase decisions"    ),    search_depth="advanced",    max_results=5,    include_raw_content=False)
```

The idea is to use targeted retrieval to validate a novelty candidate. Tavily's documentation specifically discusses selecting sources before performing full-content extraction.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://help.tavily.com\&sz=32)

Tavily Help Center+1



You can use Telem's own fetch endpoint as an alternative to Tavily Extract. You don't need both extractors for every document.

Also, since Telem already supports Tavily as a search provider, avoid accidentally performing the same Tavily search twice through different paths. The direct Tavily API should serve a distinct purpose, such as a controlled follow-up or experiment.

## **6. What convergence should actually mean**

I would distinguish three different kinds of convergence.

| Type                   | What changes?                                                                | Why it matters                                        |
| ---------------------- | ---------------------------------------------------------------------------- | ----------------------------------------------------- |
| Semantic convergence   | New documents become increasingly similar to known evidence                  | May indicate saturation or redundancy                 |
| Evidential convergence | Independent evidence supports or contradicts the same hypotheses             | Indicates whether the answer is sufficiently grounded |
| Economic convergence   | Additional searches produce progressively less useful information per dollar | Indicates when to stop searching                      |

**Economic and evidential convergence are more valuable than semantic convergence alone.**

A system can have highly similar sources and still be wrong.

Or it can have a collection of semantically diverse sources that together establish a strong answer.

Therefore, the stopping condition should not simply be “the context vector has stabilized.”

It should be something closer to:

> Stop when the important hypotheses have adequate evidence coverage and the expected benefit of another search is below its cost.

That's the part that makes this an intelligent search controller instead of an embedding filter.

## **7. The hackathon implementation I would prioritize**

I'd split the work into three components.

**First: Retrieval adapter.** Use Telem and Tavily to collect candidate URLs, titles, snippets, provider names, and source metadata. Normalize everything into one internal source object. Deduplicate by canonical URL before embedding.

**Second: Convergence engine.** Score each passage against the original intent and the existing evidence set. Maintain accepted evidence, potential discoveries, and archived sources separately. Use the novelty slider to set the exploration policy.

**Third: Demo dashboard.** Show the 3D evidence space, dynamically updated context boundaries, search calls, token consumption, and which sources entered the final answer.

For judging, I'd compare your controller against a baseline that simply sends the top five or ten retrieved results into an LLM.

The strongest proof would be that your controller retains an important minority finding while discarding duplicate content, with the resulting answer requiring fewer input tokens.

## **My recommendation**

Use **Telem for broad initial discovery**, **Tavily for targeted investigation**, and **your own convergence controller for deciding what belongs in the agent's working context**.

Keep the original question immutable. Keep the full-dimensional embeddings for all decision-making. Make the novelty slider control the search budget and exploration threshold. Treat evidence quality separately from semantic distance.

The important technical innovation is not combining Telem and Tavily. It's the decision policy determining **when additional evidence is valuable enough to justify another search**.

That gives you a concise product pitch:

**“We built a controllable convergence engine that helps search agents know what to read, what to question, and when to stop — without losing novel evidence.”**
