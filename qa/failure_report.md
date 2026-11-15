# Failure report

## BLOCKER — A URL secret stays in the canonical source key

Requirement: userinfo in a URL is not part of the canonical source key. The stored key is the host and path.

Snapshot: implementation `e8a1f68`.

Reproduction, from `/Users/bradleyharaguchi/SearchHax-QA`:

```text
/Users/bradleyharaguchi/SearchHax/exploration/.venv/bin/python -m pytest qa/tests/test_focus_userinfo.py::test_url_userinfo_is_not_part_of_the_source_key --tb=short -p no:cacheprovider --override-ini=testpaths=qa/tests
```

The input URL is `https://user:secret@news.example/a`. No live call is made.

Expected: `https://news.example/a`.

Actual: `https://user:secret@news.example/a`.

`focus/focus_attention.py` lines 47–53 set `netloc` from `parts.netloc`, which keeps the username and secret.

Deterministic.

Suggested correction: build the host from `parts.hostname` and drop userinfo.

## BLOCKER — A sentence with no question words is left out of the excerpt

Requirement: a sentence on the stored page is still sent to the model when it does not repeat the question's words.

Snapshot: implementation `e8a1f68`.

Reproduction, from `/Users/bradleyharaguchi/SearchHax-QA`:

```text
/Users/bradleyharaguchi/SearchHax/exploration/.venv/bin/python -m pytest qa/tests/test_excerpt_overlap.py::test_nonoverlapping_sentence_is_sent_to_the_model --tb=short -p no:cacheprovider --override-ini=testpaths=qa/tests
```

The page has two paragraphs. The first is `NVIDIA discussed CoreWeave capacity plans for next year.` The second is `The stake was cancelled.` The question is `What did NVIDIA announce about CoreWeave capacity?` The model is configured. No live call is made.

Expected: the model prompt contains `The stake was cancelled.`

Actual: the excerpt is only `NVIDIA discussed CoreWeave capacity plans for next year.`

`exploration/backend/extraction.py` lines 296–297 skip a paragraph with no question-token overlap once another paragraph has been chosen. The call at line 204 uses that excerpt.

Deterministic.

Suggested correction: keep the rest of the stored page in the excerpt, including sentences that do not share question tokens.

## BLOCKER — A regex hit hides a later sentence on the same page

Requirement: a disclosed-fact match does not drop the rest of the page. A later sentence is still sent to the configured model and grounded.

Snapshot: implementation `e8a1f68`.

Reproduction, from `/Users/bradleyharaguchi/SearchHax-QA`:

```text
/Users/bradleyharaguchi/SearchHax/exploration/.venv/bin/python -m pytest qa/tests/test_regex_short_circuit.py::test_later_sentence_is_not_hidden_by_the_investment_regex --tb=short -p no:cacheprovider --override-ini=testpaths=qa/tests
```

The page is `NVIDIA has invested $2 billion in CoreWeave. NVIDIA later said that investment was cancelled and the stake is zero.` The model client is configured and would quote the cancellation sentence. No live call is made.

Expected: the model is called once, and a stored relationship has object `cancelled`.

Actual: `(0, [('invested_in', 'CoreWeave', 'supported'), ('invested_amount', '$2 billion', 'supported')])`.

`exploration/backend/extraction.py` lines 106–107 return the regex batch before the model call. `exploration/backend/orchestrator.py` lines 602–603 return that same batch before the web step uses a configured model.

Deterministic.

Suggested correction: when a model is configured, ground the rest of the page as well. Do not return the regex batch before that call.

## BLOCKER — The controller ranks the search snippet, not the fetched page

Requirement: after a page is stored, the controller ranks that page. The candidate text includes the fetched sentence.

Snapshot: implementation `e8a1f68`.

Reproduction, from `/Users/bradleyharaguchi/SearchHax-QA`:

```text
/Users/bradleyharaguchi/SearchHax/exploration/.venv/bin/python -m pytest qa/tests/test_fetched_page_rank.py::test_fetched_page_is_what_the_controller_ranks --tb=short -p no:cacheprovider --override-ini=testpaths=qa/tests
```

The search snippet is `Brief.` The fetched page is `NVIDIA has invested $2 billion in CoreWeave. The buildout emphasizes advanced packaging.` The stored document version is that page. No live call is made.

Expected: the candidate text sent to the controller contains `CoreWeave`.

Actual: `['Brief.']`.

`exploration/backend/orchestrator.py` line 501 scores `document.snippet`, and line 567 stores that snippet on the candidate. The fetched page is stored as the document version and is not copied onto the candidate.

Deterministic.

Suggested correction: after the page is stored, rank and send the fetched page text. The search snippet is not a substitute for the stored page.

## BLOCKER — A fetch interaction is dropped from the session lineage

Requirement: the interaction id from a fetch stays on the investigation, with the search interaction id.

Snapshot: implementation `e8a1f68`.

Reproduction, from `/Users/bradleyharaguchi/SearchHax-QA`:

```text
/Users/bradleyharaguchi/SearchHax/exploration/.venv/bin/python -m pytest qa/tests/test_fetch_lineage.py::test_fetch_interaction_is_recorded --tb=short -p no:cacheprovider --override-ini=testpaths=qa/tests
```

The search returns session `sess-search`, interaction `int-search`, and one page URL. The fetch client returns the same session and interaction `int-fetch`, with the CoreWeave sentence as the page. No live call is made.

Expected: `interaction_ids` is `['int-search', 'int-fetch']`.

Actual: `(['int-search'], 'sess-search')`.

`exploration/backend/retrieval.py` lines 504–506 read the fetch response and discard `interaction_id`. The orchestrator records interaction ids only from the search bundle.

Deterministic.

Suggested correction: append the fetch response's `interaction_id` to `usage.interaction_ids`.

## BLOCKER — A long question is searched as its preamble

Requirement: a long question is not searched as only the sentence before the question. The search query still contains the question that follows the preamble. The stored question is unchanged.

Snapshot: implementation `e8a1f68`.

Reproduction, from `/Users/bradleyharaguchi/SearchHax-QA`:

```text
/Users/bradleyharaguchi/SearchHax/exploration/.venv/bin/python -m pytest qa/tests/test_preamble_search.py::test_long_question_keeps_the_sentence_after_the_preamble --tb=short -p no:cacheprovider --override-ini=testpaths=qa/tests
```

The question is 195 characters. It asks what share of HBM supply Samsung booked for 2027, after a background sentence. No live call is made.

Expected: the search query contains `Samsung`, and the stored question is unchanged.

Actual: `(['Please read the following background about market structure, supplier concentration, and prior reporting before you answer the actual question'], 1)`.

`exploration/backend/planner.py` lines 35–38 keep only the text before the first period when the question is longer than 180 characters. `exploration/backend/orchestrator.py` lines 341–342 search that string and increment `search_calls`.

Deterministic.

Suggested correction: when a long question is shortened, keep the text after the first sentence in the search query.

## BLOCKER — A blank snippet becomes a citation

Requirement: a candidate whose snippet is empty after stripping is not a citation. The published answer does not cite that URL.

Snapshot: implementation `e8a1f68`.

Reproduction, from `/Users/bradleyharaguchi/SearchHax-QA`:

```text
/Users/bradleyharaguchi/SearchHax/exploration/.venv/bin/python -m pytest qa/tests/test_cited_answer.py::test_blank_snippet_is_not_a_citation --tb=short -p no:cacheprovider --override-ini=testpaths=qa/tests
```

The stored quote is `NVIDIA has invested $2 billion in CoreWeave.` A second candidate has the snippet `   ` and the URL `https://news.example/empty`. The answer model returns `See [S2].` No live call is made.

Expected: the only citation URL is `https://news.example/a`, and the empty URL is not published.

Actual: `[('S1', 'NVIDIA has invested $2 billion in CoreWeave.', 'https://news.example/a'), ('S2', '   ', 'https://news.example/empty')]`.

`exploration/backend/answer.py` lines 71–82 skip a candidate only when its stripped snippet was already used. A whitespace snippet is still appended, with that whitespace as the quote.

Deterministic.

Suggested correction: do not create a citation when the snippet is empty after stripping.

## BLOCKER — No action and no stop leaves the investigation running

Requirement: a controller response with no approved action does not leave the investigation running with no stop reason. The step records a stop.

Snapshot: implementation `e8a1f68`.

Reproduction, from `/Users/bradleyharaguchi/SearchHax-QA`:

```text
/Users/bradleyharaguchi/SearchHax/exploration/.venv/bin/python -m pytest qa/tests/test_idle_controller.py::test_no_action_and_no_stop_does_not_stay_running --tb=short -p no:cacheprovider --override-ini=testpaths=qa/tests
```

The first step stores one page with the CoreWeave investment sentence. The second step's controller returns `approved_action` null, `stop` false, and `stop_reason` null. No live call is made.

Expected: status is `stopped` and a stop reason is set. `search_calls` stays 1.

Actual: `('running', None, 1)`.

`exploration/backend/orchestrator.py` lines 415–427 stop only when the decision says stop, the source is fallback, or no searches remain. This response matches none of those, so the status stays `running`.

Deterministic.

Suggested correction: when the decision has no approved action, stop the investigation. Use `no_useful_actions` when the controller did not provide a stop reason.

## BLOCKER — Blank model text is stored as a successful answer

Requirement: a model response that is empty after stripping is a blocked answer. It is not stored as a successful answer with empty markdown.

Snapshot: implementation `e8a1f68`.

Reproduction, from `/Users/bradleyharaguchi/SearchHax-QA`:

```text
/Users/bradleyharaguchi/SearchHax/exploration/.venv/bin/python -m pytest qa/tests/test_cited_answer.py::test_blank_model_text_is_not_a_successful_answer --tb=short -p no:cacheprovider --override-ini=testpaths=qa/tests
```

The stored quote is `NVIDIA has invested $2 billion in CoreWeave.` The answer model returns three spaces and a newline. No live call is made.

Expected: `blocked` is true and the markdown is empty.

Actual: `(False, '')`. `cited_markers` is empty and `llm_tokens` is 1.

`exploration/backend/answer.py` line 152 strips the body. Lines 164–172 then store that empty string with `blocked=False` when no marker remains. `exploration/backend/main.py` lines 102–106 persist that result.

Deterministic.

Suggested correction: when the stripped model text is empty, return a blocked answer. Do not store it as a successful answer.

## BLOCKER — A considered source is published without that label

Requirement: a source that was only considered, and whose snippet is not an exact quote from a stored page, is labeled as considered in the published answer. It is not presented as a verified source.

Snapshot: implementation `e8a1f68`.

Reproduction, from `/Users/bradleyharaguchi/SearchHax-QA`:

```text
/Users/bradleyharaguchi/SearchHax/exploration/.venv/bin/python -m pytest qa/tests/test_cited_answer.py::test_considered_source_is_labeled_in_the_answer --tb=short -p no:cacheprovider --override-ini=testpaths=qa/tests
```

The stored page is `NVIDIA has invested $2 billion in CoreWeave.` A candidate snippet, `Rumored capacity plans were not confirmed.`, is not in that page. The answer model cites `[S2]`. No live call is made.

Expected: the sources list says the `https://news.example/later` source is considered.

Actual: the citation status is `considered`, and the published markdown is

```text
Rumored capacity plans were not confirmed [S2].

### Sources
- [S2] Later (https://news.example/later)
```

`exploration/backend/answer.py` lines 74–82 store `status="considered"`. Lines 157–162 write the source line from the title and URL and omit the status.

Deterministic.

Suggested correction: write the citation status on each source line. A considered source must say considered.

## BLOCKER — A different NVIDIA question is searched as the CoreWeave query

Requirement: the CoreWeave retrieval query is used for the Story A question. A different question is searched with its own wording. The stored question stays the user's question.

Snapshot: implementation `e8a1f68`.

Reproduction, from `/Users/bradleyharaguchi/SearchHax-QA`:

```text
/Users/bradleyharaguchi/SearchHax/exploration/.venv/bin/python -m pytest qa/tests/test_search_rewrite.py::test_unrelated_nvidia_question_is_not_rewritten_to_coreweave --tb=short -p no:cacheprovider --override-ini=testpaths=qa/tests
```

The question is `What risks follow an NVIDIA investment if inference capacity is already sufficient for current demand and no new data-center buildout is planned?` It does not mention CoreWeave. No live call is made.

Expected: the search query is that question.

Actual: `(['NVIDIA CoreWeave investment AI factories capacity 2026'], 'What risks follow an NVIDIA investment if inference capacity is already sufficient for current demand and no new data-center buildout is planned?')`. The stored question is unchanged.

`exploration/backend/planner.py` lines 33–34 rewrite every question that contains `nvidia`, `investment`, and `capacity`.

Deterministic.

Suggested correction: use the CoreWeave query only for the Story A question. Leave a different question in its own wording.

## BLOCKER — A long question is searched as an empty query

Requirement: the retrieval query is not empty. A question that is non-empty after stripping is not sent to search as `""`, and that empty query does not spend a search.

Snapshot: implementation `e8a1f68`.

Reproduction, from `/Users/bradleyharaguchi/SearchHax-QA`:

```text
/Users/bradleyharaguchi/SearchHax/exploration/.venv/bin/python -m pytest qa/tests/test_empty_search_query.py::test_long_question_does_not_search_an_empty_query --tb=short -p no:cacheprovider --override-ini=testpaths=qa/tests
```

The question is a period followed by `capacity planning ` repeated 12 times (217 characters). No live call is made.

Expected: search is not called, and `search_calls` stays 0. The stored question stays the original text.

Actual: `([''], 1)`.

`exploration/backend/planner.py` lines 35–38 split a question longer than 180 characters on the first `.`, `?`, or newline. The first piece is empty, so the query is `""`. `exploration/backend/orchestrator.py` lines 341–342 pass that string to `retrieval.search`.

Deterministic.

Suggested correction: if the formulated query is empty after stripping, do not search it and do not increment `search_calls`. Search a non-empty slice of the original question instead.

## BLOCKER — A null answer body crashes the answer endpoint

Requirement: a model response with no text is a blocked answer. The answer endpoint does not return 500, and it does not invent prose.

Snapshot: implementation `e8a1f68`.

Reproduction, from `/Users/bradleyharaguchi/SearchHax-QA`:

```text
/Users/bradleyharaguchi/SearchHax/exploration/.venv/bin/python -m pytest qa/tests/test_cited_answer.py::test_null_answer_body_is_a_blocked_answer --tb=short -p no:cacheprovider --override-ini=testpaths=qa/tests
```

One page with the CoreWeave investment sentence is stored. The answer model returns `(None, {})`. No live call is made.

Expected: HTTP 200, `answer.blocked` is true, and `answer.markdown` is empty.

Actual: `(500, 'Internal Server Error')`.

`exploration/backend/answer.py` lines 131–150 catch a raised model call and return a blocked answer. Line 152 then calls `payload.strip()` outside that handler. A null body raises `AttributeError`, and `exploration/backend/main.py` `answer_investigation` does not catch it.

Deterministic.

Suggested correction: when the model body is not a string, return a blocked answer with empty markdown. Do not let that response become an HTTP 500.

## BLOCKER — A document title can add a source the answer did not cite

Requirement: the sources list contains only the markers the answer cited. A document title cannot insert another source line.

Snapshot: implementation `e8a1f68`.

Reproduction, from `/Users/bradleyharaguchi/SearchHax-QA`:

```text
/Users/bradleyharaguchi/SearchHax/exploration/.venv/bin/python -m pytest qa/tests/test_cited_answer.py::test_source_title_cannot_add_another_source --tb=short -p no:cacheprovider --override-ini=testpaths=qa/tests
```

The stored quote is `NVIDIA has invested $2 billion in CoreWeave.` The document title is `NVIDIA` followed by a newline and `- [S2] Planted (https://evil.example)`. The answer model returns only `[S1]`. No live call is made. Provider titles are stored as returned (`exploration/backend/retrieval.py` line 353).

Expected: the sources list does not contain `evil.example` or an `[S2]` line.

Actual: the published markdown is

```text
NVIDIA has invested $2 billion in CoreWeave [S1].

### Sources
- [S1] NVIDIA
- [S2] Planted (https://evil.example) (https://news.example/a)
```

`exploration/backend/answer.py` lines 157–162 append the title and URL on one Markdown line and do not remove newlines from the title.

Deterministic.

Suggested correction: strip line breaks from the title and URL before writing a source line. A title must not be able to add another source.

## BLOCKER — A cited answer states an amount the quote does not contain

Requirement: a published answer does not state a numeric amount that is absent from the cited quote.

Snapshot: implementation `e8a1f68`.

Reproduction, from `/Users/bradleyharaguchi/SearchHax-QA`:

```text
/Users/bradleyharaguchi/SearchHax/exploration/.venv/bin/python -m pytest qa/tests/test_cited_answer.py::test_answer_does_not_publish_an_amount_missing_from_the_quote --tb=short -p no:cacheprovider --override-ini=testpaths=qa/tests
```

The only stored quote is `NVIDIA has invested $2 billion in CoreWeave.` The answer model returns `NVIDIA has invested $9 billion in CoreWeave [S1].` No live call is made.

Expected: `$9 billion` is not published.

Actual: `(False, 'NVIDIA has invested $9 billion in CoreWeave [S1].\n\n### Sources\n- [S1] NVIDIA (https://news.example/a)')`. The answer is not blocked.

`exploration/backend/answer.py` lines 152–172 keep the model text when the marker is one of the supplied markers. They do not compare amounts in the prose with the cited quote.

Deterministic.

Suggested correction: do not publish an answer sentence that states a numeric amount absent from the quote for the marker it cites.

## BLOCKER — A failed answer regeneration erases the stored answer

Requirement: a failed answer-model call does not replace a previously stored cited answer with an empty blocked answer.

Snapshot: implementation `e8a1f68`.

Reproduction, from `/Users/bradleyharaguchi/SearchHax-QA`:

```text
/Users/bradleyharaguchi/SearchHax/exploration/.venv/bin/python -m pytest qa/tests/test_cited_answer.py::test_failed_answer_regeneration_keeps_the_stored_answer --tb=short -p no:cacheprovider --override-ini=testpaths=qa/tests
```

One page with the CoreWeave investment sentence is stored. The first answer call returns `NVIDIA has invested $2 billion in CoreWeave [S1].` The second call raises `RuntimeError`. No live call is made.

Expected: the stored answer stays unblocked and still contains that sentence.

Actual: `(True, '', 'Answer generation failed: RuntimeError')`.

`exploration/backend/main.py` lines 102–106 store `compose_answer`'s result on every call, including a blocked empty answer. `exploration/backend/answer.py` lines 142–150 return that empty answer when the model call raises.

Deterministic.

Suggested correction: when a new answer is blocked and a previous answer is already stored, keep the stored answer.

## BLOCKER — A preamble example becomes a supported relationship

Requirement: when a model response contains an example object and then the extraction payload, only the extraction payload is grounded. An example is not stored as a supported relationship.

Snapshot: implementation `e8a1f68`.

Reproduction, from `/Users/bradleyharaguchi/SearchHax-QA`:

```text
/Users/bradleyharaguchi/SearchHax/exploration/.venv/bin/python -m pytest qa/tests/test_llm_preamble.py::test_preamble_example_is_not_stored_as_supported --tb=short -p no:cacheprovider --override-ini=testpaths=qa/tests
```

The page is `NVIDIA has invested $2 billion in CoreWeave.` The model text starts with an example relationship and then returns `{"relationships": [], "gaps": []}`. No live call is made.

Expected: no supported relationship.

Actual: the example is stored as `('invested_in', 'CoreWeave', 'supported')`. The later payload is ignored.

`exploration/backend/llm.py` lines 54–77 return the first balanced `{...}`. `complete_json` parses that object, and `relationships_from_llm_payload` grounds it.

Deterministic.

Suggested correction: when more than one top-level object is present, ground the object that is the extraction payload. Do not ground an example object that precedes it.

## BLOCKER — An invented citation is published in the answer

Requirement: a synthesized answer cites only supplied markers and URLs. An unknown marker and an unknown URL are not shown.

Snapshot: implementation `ece7a3c`.

Reproduction, from `/Users/bradleyharaguchi/SearchHax-QA`:

```text
/Users/bradleyharaguchi/SearchHax/exploration/.venv/bin/python -m pytest qa/tests/test_cited_answer.py::test_invented_marker_and_url_are_not_published --tb=short -p no:cacheprovider --override-ini=testpaths=qa/tests
```

The only stored quote is `NVIDIA has invested $2 billion in CoreWeave.` The answer model returns `NVIDIA invested $2 billion [S99]. See https://evil.example/fake [S1].` No live call is made.

Expected: the published markdown contains neither `[S99]` nor `evil.example`. `cited_markers` is `["S1"]`.

Actual: the markdown is that sentence plus a Sources list for `[S1]`. `[S99]` and `https://evil.example/fake` remain in the prose. `cited_markers` is `["S1"]`.

`exploration/backend/answer.py` lines 152–162 keep the model text. They drop unknown markers only from `cited_markers`.

Deterministic.

Suggested correction: remove any `[S#]` marker that is not in the supplied citation list, and remove any URL that is not a supplied citation URL, before the markdown is stored.

## BLOCKER — The answer call ignores the LLM budget

Requirement: an answer-model call is refused when the investigation has no remaining LLM calls, and a call that does run is counted.

Snapshot: implementation `ece7a3c`.

Reproduction, from `/Users/bradleyharaguchi/SearchHax-QA`:

```text
/Users/bradleyharaguchi/SearchHax/exploration/.venv/bin/python -m pytest qa/tests/test_cited_answer.py::test_answer_call_stops_when_the_llm_budget_is_spent --tb=short -p no:cacheprovider --override-ini=testpaths=qa/tests
```

One page with the CoreWeave investment sentence is stored. `llm_calls_used` and `usage.llm_calls` are then set to `max_llm_calls` (10). `POST /api/exploration/investigations/{id}/answer` is called. The model client is injected. No live call is made.

Expected: the model is not called. The answer is blocked. `usage.llm_calls` stays 10.

Actual: `(1, False, 10)`. The model is called once, `answer.blocked` is false, and `usage.llm_calls` stays 10.

`exploration/backend/main.py` lines 102–106 call `compose_answer` and store the result. They do not read `remaining_llm_calls` and they do not increment `usage.llm_calls`.

Deterministic.

Suggested correction: do not call the answer model when `remaining_llm_calls` is 0. When a call runs, increment `llm_calls_used` and `usage.llm_calls`.

## BLOCKER — A blank approved query consumes a search

Requirement: an approved follow-up whose query is only whitespace is not searched and does not spend a search.

Snapshot: implementation `6d87f2c`.

Reproduction, from `/Users/bradleyharaguchi/SearchHax-QA`:

```text
/Users/bradleyharaguchi/SearchHax/exploration/.venv/bin/python -m pytest qa/tests/test_blank_follow_up.py::test_blank_approved_query_is_not_searched --tb=short -p no:cacheprovider --override-ini=testpaths=qa/tests
```

The first search returns one page with the CoreWeave investment sentence. The controller then approves query `"   "`. No live call is made.

Expected: the only search is `NVIDIA CoreWeave investment AI factories capacity 2026`, and `search_calls` stays 1.

Actual: the second search is `'   '`. `search_calls` is 2 and the stop reason is `budget_exhausted`.

`exploration/backend/orchestrator.py` lines 400–402 pass `action.query` to `retrieval.search` after checking duplicates with `strip()`, but they do not reject a query that is empty after stripping.

Deterministic.

Suggested correction: do not search a query that is empty after stripping whitespace. Leave that search unspent.

## BLOCKER — An archived page drops the open follow-up

Requirement: an unresolved question above the utility floor still produces its follow-up search when one search remains. Archiving the current page does not cancel that search.

Snapshot: implementation `6d87f2c`.

Reproduction, from `/Users/bradleyharaguchi/SearchHax-QA`:

```text
/Users/bradleyharaguchi/SearchHax/exploration/.venv/bin/python -m pytest qa/tests/test_focus_archive.py::test_archived_page_does_not_drop_the_open_follow_up --tb=short -p no:cacheprovider --override-ini=testpaths=qa/tests
```

The only page is `NVIDIA has invested $2 billion in CoreWeave. The buildout emphasizes advanced packaging.` The profile interest is `advanced packaging`. No live call is made. `focus_post` is the controller.

Expected: `search_calls` is 2. One search remains, and the open questions are above the 0.15 floor.

Actual: `('low_expected_value', 1, [(0.8, 'What grounded evidence connects the investigation to the open interest: advanced packaging?'), (0.85, 'What downstream customer demand or product revenue is tied to the NVIDIA CoreWeave capacity expansion?')])`. The rationale says Focus archived every candidate. `approved_action` is null.

`exploration/backend/focus_bridge.py` lines 69–84 approve a search only when some passage is `investigate`. Lines 91–93 stop with `low_expected_value` when every passage is `archive`, before the pending actions are read.

Deterministic.

Suggested correction: when a pending action's utility is at least `budget.min_utility` and a search remains, approve that action. Archiving the current page does not by itself stop the investigation.

## BLOCKER — A blank question is stored as an empty investigation

Requirement: the investigation question is the user's question. A body whose question is only whitespace is rejected and no investigation is stored.

Snapshot: implementation `6d87f2c`.

Reproduction, from `/Users/bradleyharaguchi/SearchHax-QA`:

```text
/Users/bradleyharaguchi/SearchHax/exploration/.venv/bin/python -m pytest qa/tests/test_blank_question.py::test_blank_question_is_rejected --tb=short -p no:cacheprovider --override-ini=testpaths=qa/tests
```

The request body is `{"question": " "}`. No search is run.

Expected: HTTP 422, and no investigation is stored.

Actual: HTTP 200. The stored question is `""`.

`CreateInvestigationRequest.question` has `min_length=1`, so one space passes. `Orchestrator.create` in `exploration/backend/orchestrator.py` line 75 stores `question.strip()`, which is empty.

Deterministic. No network call.

Suggested correction: reject a question that is empty after stripping whitespace. Do not create the investigation.

## BLOCKER — A hypothesis quote is stored as a supported relationship

Requirement: a relationship the model marks as a hypothesis does not become a supported edge. `hypothesis` is its own status.

Snapshot: implementation `6d87f2c`.

Reproduction, from `/Users/bradleyharaguchi/SearchHax-QA`:

```text
/Users/bradleyharaguchi/SearchHax/exploration/.venv/bin/python -m pytest qa/tests/test_hypothesis_status.py::test_hypothesis_quote_is_not_a_supported_relationship --tb=short -p no:cacheprovider --override-ini=testpaths=qa/tests
```

The page is `NVIDIA may expand capacity next year.` The payload has one relationship, kind `hypothesis`, quote `NVIDIA may expand capacity`. No model is called.

Expected: no relationship has status `supported`.

Actual: `[('hypothesis', 'supported', 'may expand', 'capacity')]`.

`relationships_from_llm_payload` passes the row to `_add_grounded`. `decide_status` in `exploration/backend/verification.py` lines 47–54 returns `supported` when the quote is an exact substring and contains the subject and object. It does not read `kind`. The baseline counter `hypothesis_relationships` only counts status `hypothesis`, so this edge is counted as supported.

Deterministic.

Suggested correction: when `kind` is `hypothesis`, store status `hypothesis`. Do not mark it `supported`.

## BLOCKER — The committed evidence schema omits the profile, the answer, and knowledge value

Requirement: `shared/evidence.schema.json` matches the committed exploration models, including the research profile, the cited answer, and the knowledge-value score.

Snapshot: implementation `ece7a3c`.

Reproduction, from `/Users/bradleyharaguchi/SearchHax-QA`:

```text
/Users/bradleyharaguchi/SearchHax/exploration/.venv/bin/python -m pytest qa/tests/test_contract_schema.py::test_committed_schema_includes_profile_and_knowledge_value --tb=short -p no:cacheprovider --override-ini=testpaths=qa/tests
```

Expected: the schema defines `AnswerCitation`, `GroundedAnswer`, `KnowledgeValue`, `KnownClaim`, and `ResearchProfile`. `ExplorationExport` has `answer` and `profile`. `EvidenceCandidate` has `knowledge_value`.

Actual: `(['AnswerCitation', 'GroundedAnswer', 'KnowledgeValue', 'KnownClaim', 'ResearchProfile'], ['answer', 'profile'], ['knowledge_value'])`.

`shared/contracts.py` `ExplorationExport.model_json_schema()` includes them. `write_contract_files` is the writer for `shared/evidence.schema.json`, and the committed file was not regenerated after the profile fields were added.

Deterministic. No network call.

Suggested correction: regenerate `shared/evidence.schema.json` from the committed models. Do not drop `profile` or `knowledge_value` from the models.

## BLOCKER — A truncated-excerpt note becomes the next search

Requirement: a model note that the excerpt was cut off is not an unresolved research question and is not a follow-up query. The stored investigation question stays the user's question.

Snapshot: implementation `6d87f2c`.

`demo/integrated_profile_evaluation.json` stores this open question: `The excerpt is truncated mid-sentence at the funding statement ('supported by Cont'), so the funding source and study details are unavailable.`

Reproduction, from `/Users/bradleyharaguchi/SearchHax-QA`:

```text
/Users/bradleyharaguchi/SearchHax/exploration/.venv/bin/python -m pytest qa/tests/test_extraction_gaps.py::test_truncated_excerpt_note_is_not_a_follow_up_query --tb=short -p no:cacheprovider --override-ini=testpaths=qa/tests
```

No live model is called. The payload has no relationships and one gap whose text is that note.

Expected: the note is not stored as a gap, and no search action uses it as the query.

Actual: `relationships_from_llm_payload` stores it as a gap with `missing_evidence` 1.0. `generate_actions` uses the note as the query. Utility is 0.5, above the 0.15 floor.

`exploration/backend/extraction.py` lines 167–189 append every gap string. `exploration/backend/planner.py` lines 133–137 use that text as the query when the kind is `gap`.

The same file also stores `The excerpt contains only a disclaimer and does not discuss NVIDIA, its investments, GPU customers, or AI capacity expansion, so the research question cannot be addressed from this text.` That sentence takes the same path.

Deterministic.

Suggested correction: do not store a gap that describes the excerpt, a truncation, or a disclaimer. Leave the user's question unchanged and do not search that note.

## BLOCKER — A quarter number is rewritten into a source citation

Requirement: a bare parenthetical number is not a citation. The answer does not attach a source to "quarter (1)".

Snapshot: implementation `31c389b`. Uncommitted `exploration/backend/orchestrator.py`, `pyproject.toml`, and `exploration/tests/test_integrated_pipeline.py` were not imported.

Reproduction, from `/Users/bradleyharaguchi/SearchHax-QA`:

```text
/Users/bradleyharaguchi/SearchHax/exploration/.venv/bin/python -m pytest qa/tests/test_focus_parenthetical.py::test_quarter_number_is_not_a_source_citation --tb=short -p no:cacheprovider --override-ini=testpaths=qa/tests
```

No live model is called. The only source is `https://example.com/price`. The model text is `Demand fell in quarter (1).` The call uses `strict_citations=False`.

Expected: the markdown still contains `(1)`, and `cited_source_ids` is empty.

Actual: `Demand fell in quarter [S1].` The Sources section lists `[S1]` as `https://example.com/price`. `cited_source_ids` is `("S1",)`.

`focus/answer_composer.py` line 20 is `_PAREN_CITATION_RE = re.compile(r"\((?:source\s*)?(S\d+|\d+)\)", re.IGNORECASE)`. The `source` prefix is optional, so `(1)` matches. Lines 138–143 replace it with `[S1]`.

Deterministic.

Suggested correction: rewrite `(source 1)` and `(S1)` only. Leave a bare `(1)` unchanged.

## BLOCKER — The default search plan spends the budget before the investigate follow-up

Requirement: a passage routed to investigate is searched within the default budget of 3. Fixed angles do not consume that budget ahead of it.

Snapshot: implementation `31c389b`. Uncommitted `exploration/backend/orchestrator.py` was not imported.

Reproduction, from `/Users/bradleyharaguchi/SearchHax-QA`:

```text
/Users/bradleyharaguchi/SearchHax/exploration/.venv/bin/python -m pytest qa/tests/test_focus_plan.py::test_investigate_follow_up_runs_inside_the_default_budget --tb=short -p no:cacheprovider --override-ini=testpaths=qa/tests
```

No live provider is called. The plan is the five angles in `focus/app.py` lines 77–85. `max_search_calls` is 3, the slider default. The first retrieve returns two passages. The second is routed to `investigate` with title `Battery resale`.

Expected: the queries include `electric vehicle demand Battery resale supporting evidence conflicting evidence`.

Actual: `['electric vehicle demand', 'electric vehicle demand main causes evidence', 'electric vehicle demand evidence challenging the premise']`. `search_calls` is 3 and `queued` is 1.

`focus/research_loop.py` line 38 places the whole plan ahead of any follow-up. Line 52 appends the investigate query after those angles. The loop stops at line 40 before that query is popped.

Deterministic.

Suggested correction: run an investigate follow-up before the remaining generic angles, or reserve a call for it inside the budget of 3.

## BLOCKER — A longer URL is rewritten into a citation of a shorter source

Requirement: a citation names the page that was written. A URL that only begins with a source URL is not replaced with that source's marker.

Snapshot: implementation `31c389b`.

Reproduction, from `/Users/bradleyharaguchi/SearchHax-QA`:

```text
/Users/bradleyharaguchi/SearchHax/exploration/.venv/bin/python -m pytest qa/tests/test_focus_url_citation.py::test_longer_url_is_not_cited_as_the_shorter_source --tb=short -p no:cacheprovider --override-ini=testpaths=qa/tests
```

No live model is called. The only source is `https://example.com/price`. The model text is `A different page https://example.com/price-war says demand rose.` The call uses `strict_citations=False`.

Expected: the markdown still contains `https://example.com/price-war`, it does not contain `[S1]-war`, and `cited_source_ids` is empty.

Actual: `A different page [S1]-war says demand rose.` The Sources section lists `[S1]` as `https://example.com/price`. `cited_source_ids` is `("S1",)`.

`focus/answer_composer.py` `_normalize_citations` lines 144–146 replace any occurrence of the source URL, including when it is only a prefix of a longer URL.

Deterministic. This rewrite was added in `31c389b`.

Suggested correction: replace a source URL only when it is the whole URL, not a prefix of a longer one. Do not cite `https://example.com/price` for `https://example.com/price-war`.

The nineteen failures from `fd2aa11` still fail on this commit. Focus unit tests: 24 passed.

## BLOCKER — A cached page is stored with cache_hits at zero

Requirement: measured usage counts a page that was read from the fetch cache. `cache_hits` is not left at zero when the provider fetch function was not called.

Snapshot: implementation `31c389b`. Retested; this failure still occurs.

Reproduction, from `/Users/bradleyharaguchi/SearchHax-QA`:

```text
/Users/bradleyharaguchi/SearchHax/exploration/.venv/bin/python -m pytest qa/tests/test_cache_metrics.py::test_cached_fetch_increments_cache_hits --tb=short -p no:cacheprovider --override-ini=testpaths=qa/tests
```

No live provider is called. Two investigations share one cache directory. The page is `NVIDIA has invested $2 billion in CoreWeave.` The first run calls fetch once. The second run does not call fetch and still stores one document.

Expected: the second investigation's `usage.cache_hits` is 1.

Actual: `assert 0 == 1`. The second usage is `cache_hits=0`, `urls_fetched=0`, `fetch_calls=1`, and one document is stored.

`exploration/backend/retrieval.py` lines 176–179 reuse a cached body and set `from_cache`. Nothing in the backend assigns `UsageMetrics.cache_hits`. The orchestrator does not read `from_cache`.

Deterministic.

Suggested correction: when a stored page comes from the fetch cache, increment `usage.cache_hits`. Do not report zero cache hits for that page.

The same gap is in the recorded run `demo/integrated_profile_evaluation.json` on `6d87f2c`. That file lists 8 candidate URLs. `urls_fetched` is 5 and `cache_hits` is 0. The local search history for `inv_99aa92ab6bb5459e` shows why the second search still ran. The first search returned 6 URLs and 5 were stored. The second search returned 6 URLs and 3 of those were stored (`sbsheriff.org`, `ojp.gov`, and `regulation.govt.nz`). The fetch budget counts only URLs that were not already cached, so three uncounted cache hits left room for three more network fetches. `cache_hits` stayed 0, which makes 5 fetches look like they produced 8 stored pages.

```text
/Users/bradleyharaguchi/SearchHax/exploration/.venv/bin/python -m pytest qa/tests/test_profile_value.py::test_recorded_profile_run_counts_every_stored_page --tb=short -p no:cacheprovider --override-ini=testpaths=qa/tests
```

Expected: `5 + cache_hits == 8`. Actual: `(5, 0, 8)`.

## BLOCKER — A possessive CoreWeave match is stored as an investment in CoreWeave

Requirement: a supported edge matches the claim in the stored sentence. Cutting the sentence at CoreWeave does not make CoreWeave the object.

Snapshot: implementation `31c389b`. Retested; this failure still occurs.

Reproduction, from `/Users/bradleyharaguchi/SearchHax-QA`:

```text
/Users/bradleyharaguchi/SearchHax/exploration/.venv/bin/python -m pytest qa/tests/test_provider_and_budget.py::test_possessive_coreweave_is_not_an_investment_in_coreweave --tb=short -p no:cacheprovider --override-ini=testpaths=qa/tests
```

No live provider is called. The page is `NVIDIA has invested $2 billion in CoreWeave's rival Lambda.`

Expected: no supported `invested_in` edge whose object is CoreWeave. If a span is stored, it includes `rival`.

Actual: one supported `invested_in` relationship with object CoreWeave. The stored span is `NVIDIA has invested $2 billion in CoreWeave`. `rival` is not in the span. `invested_amount` `$2 billion` is also supported.

`exploration/backend/extraction.py` line 236 is `_INVESTMENT = re.compile(r"NVIDIA has invested (?P<amount>\$[\d.]+ billion) in (?P<company>CoreWeave)")`. There is no word boundary after CoreWeave, so `CoreWeave's` matches. `_extract_disclosed_facts` stores `match.group(0)`.

Deterministic.

Suggested correction: require a word boundary after CoreWeave. Do not mark `invested_in` CoreWeave supported when the sentence continues with `'s`.

## BLOCKER — A Tavily failure discards pages Telem already returned

Requirement: one provider failing does not drop passages the other provider returned. The failure is recorded.

Snapshot: implementation `31c389b`. Retested; this failure still occurs.

Reproduction, from `/Users/bradleyharaguchi/SearchHax-QA`:

```text
/Users/bradleyharaguchi/SearchHax/exploration/.venv/bin/python -m pytest qa/tests/test_focus_providers.py::test_one_provider_failure_keeps_the_other_providers_pages --tb=short -p no:cacheprovider --override-ini=testpaths=qa/tests
```

No live provider is called. `search(..., "both")` is used. Telem returns `https://telem.example`. Tavily raises `RuntimeError: tavily unavailable`.

Expected: the call returns the Telem page. The Tavily error is recorded.

Actual: `('RuntimeError', [], ['telem', 'tavily'])`. Telem ran, then Tavily ran, and the returned list is empty because the exception left `search`.

`focus/retrieval_adapters.py` lines 213–217 append each provider's rows and do not catch a provider exception. The Telem rows are local to that call and are discarded.

Deterministic.

Suggested correction: keep the passages from the provider that succeeded and record the other provider's error. Do not raise those passages away.

## BLOCKER — An unknown citation stays in an answer that also has a valid one

Requirement: an unknown citation marker is rejected. A displayed answer does not contain a source id that was not supplied.

Snapshot: implementation `31c389b`. Retested; this failure still occurs.

Reproduction, from `/Users/bradleyharaguchi/SearchHax-QA`:

```text
/Users/bradleyharaguchi/SearchHax/exploration/.venv/bin/python -m pytest qa/tests/test_focus_answer.py::test_unknown_marker_is_not_shown_with_a_valid_citation --tb=short -p no:cacheprovider --override-ini=testpaths=qa/tests
```

No live model is called. The only considered source is `https://example.com/price`. The model text is `An invented statistic [S99]. Affordability matters [S1].` The call uses `strict_citations=False`, which is what `focus/app.py` lines 87–89 pass.

Expected: the call raises `AnswerGenerationError`, or the returned markdown does not contain `[S99]`.

Actual: the markdown is:

```text
An invented statistic [S99]. Affordability matters [S1].

### Sources
- [S1] [EV affordability](https://example.com/price)
```

`cited_source_ids` is `("S1",)`. `focus/app.py` lines 91–92 warn only when that tuple is empty, so this answer is shown with no warning.

`focus/answer_composer.py` lines 262–268 drop `[S99]` from the source list and leave it in the prose.

Deterministic.

Suggested correction: reject the answer when any citation marker is not one of the supplied source ids, including when another marker is valid. Do not render `[S99]`.

## BLOCKER — The focus loop searches the same follow-up twice

Requirement: a follow-up query is not executed twice. The search budget is spent on a new query.

Snapshot: implementation `31c389b`. Retested; this failure still occurs.

Reproduction, from `/Users/bradleyharaguchi/SearchHax-QA`:

```text
/Users/bradleyharaguchi/SearchHax/exploration/.venv/bin/python -m pytest qa/tests/test_focus_loop.py::test_identical_follow_up_is_issued_once --tb=short -p no:cacheprovider --override-ini=testpaths=qa/tests
```

No live provider is called. The first retrieve returns three passages. Two of them are routed to `investigate` and both have the title `EV demand`. `max_search_calls` is 3.

Expected: each query string is issued once.

Actual: `['electric vehicle demand', 'electric vehicle demand EV demand supporting evidence conflicting evidence', 'electric vehicle demand EV demand supporting evidence conflicting evidence']`

`focus/research_loop.py` lines 46–49 queue a follow-up for every `investigate` source key. `followup_query` uses the title, so the two titles produce one string and it is still appended twice. The third allowed call repeats the second.

Deterministic.

Suggested correction: do not append a follow-up that is already queued or already issued.

## BLOCKER — A failed Focus fetch body replaces the search snippet

Requirement: a failed URL is skipped. The answer path keeps the search snippet instead of the error page.

Snapshot: implementation `31c389b`. Retested; this failure still occurs.

Reproduction, from `/Users/bradleyharaguchi/SearchHax-QA`:

```text
/Users/bradleyharaguchi/SearchHax/exploration/.venv/bin/python -m pytest qa/tests/test_focus_fetch.py::test_failed_fetch_body_is_not_used_as_page_text --tb=short -p no:cacheprovider --override-ini=testpaths=qa/tests
```

No live provider is called. The mocked Telem fetch returns one row: url `https://news.example/missing`, status `failed`, error `HTTP 404`, content `404 Not Found. NVIDIA has invested $2 billion in CoreWeave.`

Expected: `telem_fetch` omits that URL. A `consider` passage keeps the text `Search snippet only.`

Actual: `AssertionError: assert 'https://news.example/missing' not in {'https://news.example/missing': '404 Not Found. NVIDIA has invested $2 billion in CoreWeave.'}`

`hydrate_decisions` then replaces the snippet with that body. `focus/retrieval_adapters.py` `telem_fetch` lines 144–148 keep any nonempty `content` and never read `status` or `error`. The docstring says failed URLs are skipped.

Deterministic.

Suggested correction: skip a row whose status is failed or error, or whose error field is set, even when content is nonempty. Leave the search snippet in place.

The thirteen exploration blockers below still fail on this commit. Exploration sources match `408edb3`.

## BLOCKER — A fetch exception commits the search and then leaves the counters at zero

Requirement: search counters and search history stay consistent. A network failure is recorded. The step does not abort after part of the write has committed.

Snapshot: implementation `31c389b`. Retested; this failure still occurs. Exploration sources match `408edb3`.

Reproduction:

```text
/Users/bradleyharaguchi/SearchHax/exploration/.venv/bin/python -m pytest qa/tests/test_provider_and_budget.py::test_fetch_exception_does_not_split_the_search_counter --tb=short -p no:cacheprovider --override-ini=testpaths=qa/tests
```

Search returns one URL. Fetch raises `ConnectionError: fetch failed`. No live provider is called.

Expected: `step` returns. Status is `stopped` or `blocked`. `searches_used`, `search_calls`, and the search-history length are equal. No document is stored.

Actual: `step` raises `ConnectionError`. Status stays `created`. Search history contains `NVIDIA CoreWeave investment AI factories capacity 2026`. `searches_used` is 0 and `search_calls` is 0. `blocker` is empty. The next `step` sees no documents and `search_calls` 0, so it treats the investigation as not started and can search again.

Location: `exploration/backend/orchestrator.py` `_record_search` runs before `_ingest_bundle`. `database.py` `insert_search` commits at line 422. The fetch exception is not caught, and the investigation row is never updated.

Deterministic: yes.

Suggested correction: record the fetch error on the investigation and keep `searches_used` equal to the history length. Do not leave status `created` after a committed search row.

## BLOCKER — A raised provider error escapes the investigation step

Requirement: a network failure is explicit. Bounded retries are fine. After those retries the investigation records the failure instead of aborting the step.

Snapshot: implementation `31c389b`. Retested; this failure still occurs. Exploration sources match `408edb3`.

Reproduction:

```text
/Users/bradleyharaguchi/SearchHax/exploration/.venv/bin/python -m pytest qa/tests/test_provider_and_budget.py::test_search_exception_is_recorded_instead_of_escaping --tb=short -p no:cacheprovider --override-ini=testpaths=qa/tests
```

The search function raises `Unavailable` with `status_code` 503 and message `provider unavailable`. No live provider is called.

Expected: `step` returns an export whose status is `stopped` or `blocked`, and the blocker, stop reason, or rationale contains `503`, `unavailable`, or `error`. No document is stored. Fetch is not called. The provider is called at most 3 times.

Actual: `step` raises `Unavailable: provider unavailable`. A direct call left the stored investigation at status `created`, with `blocker` empty, `search_calls` 0, and 3 provider attempts.

Location: `exploration/backend/orchestrator.py` lines 291–298 catch only `BudgetExceededError`. `exploration/backend/retrieval.py` `call_with_retries` retries status 503 and then re-raises at line 312.

Deterministic: yes.

Suggested correction: catch the search exception after the existing retries, set `blocker` to that error, set status to `stopped`, and set `stop_reason` to `unresolved_uncertainty`. Do not invent documents.

## BLOCKER — An empty failed fetch stays `running` and drops the error

Requirement: a network failure is explicit. A fetch that returns an error and no page is not a successful investigation step.

Snapshot: implementation `31c389b`. Retested; this failure still occurs. Exploration sources match `408edb3`.

Reproduction:

```text
/Users/bradleyharaguchi/SearchHax/exploration/.venv/bin/python -m pytest qa/tests/test_provider_and_budget.py::test_empty_failed_fetch_is_recorded --tb=short -p no:cacheprovider --override-ini=testpaths=qa/tests
```

Search returns `https://news.example/missing`. Fetch returns `status` `error`, `error` `HTTP 404`, and an empty body. No live provider is called.

Expected: status is `stopped`, and the blocker, stop reason, or rationale contains `404`, `error`, or `unavailable`. No document is stored.

Actual: status stays `running`. `blocker`, `stop_reason`, and rationale are empty. Documents and relationships are empty. `fetch_calls` is 1 and `urls_fetched` is 1.

Location: `exploration/backend/orchestrator.py` lines 472–474 skip a page with no content and never read `page.status` or `page.error`.

Deterministic: yes.

Suggested correction: when every fetched page has an error or no content, set `blocker` to those errors, set status to `stopped`, and set `stop_reason` to `unresolved_uncertainty`.

## BLOCKER — A failed fetch body is stored as supported evidence

Requirement: a network failure is explicit, and a page that was not retrieved does not become a verified source. Citation integrity requires the quotation to come from the fetched source, not from an error body.

Snapshot: implementation `31c389b`. Retested; this failure still occurs. Exploration sources match `408edb3`. Same behavior as `2c8133a`.

Reproduction:

```text
/Users/bradleyharaguchi/SearchHax/exploration/.venv/bin/python -m pytest qa/tests/test_provider_and_budget.py::test_failed_fetch_body_is_not_stored_as_evidence qa/tests/test_provider_and_budget.py::test_failed_fetch_is_not_replayed_from_cache --tb=short -p no:cacheprovider --override-ini=testpaths=qa/tests
```

Search returns `https://news.example/missing`. Fetch returns `status` `error`, `error` `HTTP 404`, and a body that begins `404 Not Found` and also contains `NVIDIA has invested $2 billion in CoreWeave.` No live provider is called. A second investigation then uses the same cache with a fetch function that would return the real page.

Expected: no source document is stored and no relationship is `supported`. The second investigation calls fetch.

Actual: one document is stored. `invested_in` `CoreWeave` and `invested_amount` `$2 billion` are both `supported`. Status stays `running` and `blocker` is empty. The second fetch function is not called. The stored page still begins `404 Not Found`, and both edges are `supported` again.

Location: `exploration/backend/orchestrator.py` line 472 uses `page.content` and does not read `page.status` or `page.error`. `exploration/backend/retrieval.py` line 215 writes that body into the fetch cache, and line 176 reuses any cached object that has content.

Deterministic: yes.

Suggested correction: do not store or cache a page whose status is `error` or whose error field is set. Record the fetch error on the investigation. Do not extract relationships from that body. A later fetch of the same URL has to reach the provider.

## BLOCKER — The string `false` becomes a stop and drops the approved search

Requirement: a controller approval runs that query. A value that is not a boolean is not a stop. A malformed body is rejected as fallback rather than recorded as a convergence decision.

Snapshot: implementation `2c8133a`.

Reproduction:

```text
/Users/bradleyharaguchi/SearchHax/exploration/.venv/bin/python -m pytest qa/tests/test_focus_and_versions.py::test_string_false_stop_does_not_drop_the_approved_search --tb=short -p no:cacheprovider --override-ini=testpaths=qa/tests
```

The first page is `NVIDIA has invested $2 billion in CoreWeave.` The demand gap stays open. The controller then returns `stop` as the string `false`, a rationale, and an approved action whose query is `independent measurement of CoreWeave customer demand`. No live provider is called.

Expected: that query is searched and `stop` is false, or the payload is rejected and `decision_source` is `fallback`.

Actual: one search ran. `decision.stop` is true, `approved_action` is null, `stop_reason` is null, `decision_source` is `convergence`, and status stays `running`.

Location: `exploration/backend/convergence.py` line 79 uses `bool(data.get("stop", ...))`. In Python `bool("false")` is true, so line 85 clears `approved_action`. `orchestrator.py` then applies a stop only when `stop_reason` is also set, so the investigation stays `running` and the search never happens.

Deterministic: yes.

Suggested correction: accept `stop` only when it is a boolean. The string `false` is not a stop. If the field is some other type, reject the payload and use the fallback.

## BLOCKER — The web loop labels a shared wire and then drops the cluster and the contradiction

Requirement: pages that cite one announcement are one origin, and a derivative amount is not stored as a second supported fact. `run_story_c` does this. The search/fetch loop does not.

Snapshot: implementation `8e3e6e5`.

Reproduction:

```text
/Users/bradleyharaguchi/SearchHax/exploration/.venv/bin/python -m pytest qa/tests/test_provider_and_budget.py::test_web_path_keeps_story_c_wire_as_one_origin_and_one_amount --tb=short -p no:cacheprovider --override-ini=testpaths=qa/tests
```

One mocked search returns `https://lumenarc.example/press/series-d` (`FOR IMMEDIATE RELEASE`, `$400 million`, `LF-PR-2026-031`) and `https://voltstreet.example/lumenarc` (`$480 million`, same wire). No live provider is called.

Expected: `origin_clusters` contains `LF-PR-2026-031` with both documents, `$400 million` stays `supported`, and `$480 million` is not `supported`.

Actual: the test fails because `origin_clusters` is empty. The provenance rows are already `original` and `derivative` with `origin_id` `LF-PR-2026-031`. Both `raised_amount` edges are `supported`, and `contradictions` is empty.

Location: `exploration/backend/orchestrator.py` `_ingest_bundle` calls `classify_provenance` for `.example` URLs around lines 482–493. `origin_clusters` and `reconcile_amount_conflicts` are called only from `run_story_c` at lines 160 and 159.

Deterministic: yes.

Suggested correction: after web ingest, build the origin clusters from the provenance rows and run the same amount reconciliation used by Story C.

## BLOCKER — A causal demand sentence closes the gap without evidence

Requirement: a link from the investment to future product demand is a hypothesis until separate evidence supports it. Naming demand in a causal sentence is not that evidence, and it does not answer the open demand question.

Snapshot: implementation `8e3e6e5`.

Reproduction:

```text
/Users/bradleyharaguchi/SearchHax/exploration/.venv/bin/python -m pytest qa/tests/test_provider_and_budget.py::test_causal_demand_sentence_does_not_close_the_gap --tb=short -p no:cacheprovider --override-ini=testpaths=qa/tests
```

The fetched page is: `NVIDIA has invested $2 billion in CoreWeave. That investment caused customer demand for AI factories to rise.` No live provider is called. The controller is down.

Expected: the demand question stays open, or a demand relationship is stored as `hypothesis` or `insufficient`. No causation edge is `supported`.

Actual: `unresolved_questions` is empty and there is no demand relationship. `invested_in` and `invested_amount` are `supported`. The next fallback step stops with `no_useful_actions` because nothing is left to ask.

Location: `exploration/backend/extraction.py` line 267 treats any match of `customer demand`, `downstream demand`, or `product revenue` as demand already stated, so the gap at lines 268–276 is skipped. The causal sentence is never stored.

Deterministic: yes.

Suggested correction: keep the demand question open unless a grounded, non-causal measurement of demand is extracted. If the causal sentence is stored, its status is `hypothesis`, not `supported`.

## BLOCKER — A denial that contains the investment wording becomes supported

Requirement: unsupported assertions do not become supported graph edges. A quotation has to keep the sentence that qualifies it. Preserving only the matching clause drops the denial.

Snapshot: implementation `8e3e6e5`.

Reproduction:

```text
/Users/bradleyharaguchi/SearchHax/exploration/.venv/bin/python -m pytest qa/tests/test_provider_and_budget.py::test_negated_investment_sentence_is_not_supported --tb=short -p no:cacheprovider --override-ini=testpaths=qa/tests
```

The fetched page is: `The rumor that NVIDIA has invested $2 billion in CoreWeave is unconfirmed and is not in the filing.` No live provider is called.

Expected: no relationship from that page has status `supported`.

Actual: `invested_amount` `$2 billion` and `invested_in` `CoreWeave` are both `supported`. The stored span text is `NVIDIA has invested $2 billion in CoreWeave`, which is an exact substring, and the words `rumor` and `unconfirmed` are not in the span.

Location: `exploration/backend/extraction.py` line 236 matches that clause. `_extract_disclosed_facts` at line 252 passes only `match.group(0)` to `_add_grounded`. `decide_status` then marks the clause supported because `NVIDIA` and `CoreWeave` occur inside it. The surrounding sentence is not checked.

Deterministic: yes.

Suggested correction: do not mark a match supported when the enclosing sentence negates or qualifies it (`rumor`, `unconfirmed`, `not in the filing`). Store the enclosing sentence as the span, or downgrade the edge to `insufficient`.

## BLOCKER — The web loop accepts two contradictory amounts as supported

Requirement: contradictory claims are not accepted together without qualification. Provenance verification labels conflict. Story C does this. A normal web investigation does not.

Snapshot: implementation `8e3e6e5`.

Reproduction:

```text
/Users/bradleyharaguchi/SearchHax/exploration/.venv/bin/python -m pytest qa/tests/test_provider_and_budget.py::test_web_path_does_not_accept_two_amounts_as_supported --tb=short -p no:cacheprovider --override-ini=testpaths=qa/tests
```

One mocked search returns two pages. One says `NVIDIA has invested $2 billion in CoreWeave.` The other says `NVIDIA has invested $5 billion in CoreWeave.` Both quotations match the stored page text. No live provider is called.

Expected: a contradiction is recorded, or the two `invested_amount` edges are not both `supported`.

Actual: both edges are `supported`, `contradictions` is empty, and each edge's notes are empty.

Location: `exploration/backend/orchestrator.py` calls `reconcile_amount_conflicts` only from `run_story_c` (line 159). `_ingest_bundle` appends relationships and never reconciles them. Web pages that are not `*.example` are stored with `origin_kind` `unknown` at lines 485–491, so even a later reconcile would not know which page is the original.

Deterministic: yes.

Suggested correction: after web extraction, run the same conflict check used for Story C. Do not leave two different amounts for the same subject and predicate `supported` with an empty contradiction list.

## BLOCKER — A total provider outage stays `running` and drops the error

Requirement: network failures are handled explicitly. A search where every provider fails must stop, and the failure must be visible on the investigation. It must not invent documents.

Snapshot: implementation `8e3e6e5`.

Reproduction:

```text
/Users/bradleyharaguchi/SearchHax/exploration/.venv/bin/python -m pytest qa/tests/test_provider_and_budget.py::test_provider_outage_is_recorded_and_the_investigation_stops --tb=short -p no:cacheprovider --override-ini=testpaths=qa/tests
```

The mocked search returns Brave status 503 `unavailable` and Tavily status 429 `rate limit`, both with empty results. No fetch runs. No live provider is called.

Expected: `status` is `stopped`, and `blocker`, `stop_reason`, or `decision_rationale` names the 503, the 429, or the provider error text. `documents` and `relationships` stay empty.

Actual: `status` is `running`, `stop_reason` is null, `blocker` is null, and `decision_rationale` is empty. `documents` and `relationships` are empty. One search was consumed.

Location: `exploration/backend/retrieval.py` keeps the failures on `SearchBundle.provider_errors`, and the stored `raw.provider_runs` at lines 396–405 keep provider and status but drop `error`. `exploration/backend/orchestrator.py` `_initial_web_step` lines 292–310 only stops when `live_extraction_blocked` is set. An empty result set never sets that flag, so the outage is discarded and the investigation stays `running`.

Deterministic: yes.

Suggested correction: when `provider_errors` is non-empty and no document content was stored, set `blocker` to those errors, set status to `stopped`, and set `stop_reason` to `unresolved_uncertainty`.

## BLOCKER — A controller stop without a reason code leaves the investigation running

Requirement: a valid controller response leads to the corresponding action. `stop: true` ends the investigation, so status becomes `stopped`.

Snapshot: implementation `8e3e6e5`.

Reproduction:

```text
/Users/bradleyharaguchi/SearchHax/exploration/.venv/bin/python -m pytest qa/tests/test_focus_and_versions.py::test_controller_stop_without_reason_code_still_stops --tb=short -p no:cacheprovider --override-ini=testpaths=qa/tests
```

The first step retrieves one mocked page containing `NVIDIA has invested $2 billion in CoreWeave.` The second step posts to a controller that returns `{"stop": true, "rationale": "controller says stop without a reason code"}`. No live provider is called.

Expected: `status` is `stopped` and `stop_reason` is set. A third step does not search.

Actual: `decision.stop` is true, `decision.decision_source` is `convergence`, `decision.stop_reason` is null, and `investigation.status` stays `running`. The third step also stays `running`. The provider was called once.

Location: `exploration/backend/convergence.py` line 87 stores `stop_reason` only when the code is one of the five literals, so a missing code becomes null. `exploration/backend/orchestrator.py` line 355 applies the stop only when both `decision.stop` and `decision.stop_reason` are set. The same conjunction is at line 237 for Story C. A later step returns immediately only when status is already `stopped` or `blocked`.

Deterministic: yes.

Suggested correction: when `decision.stop` is true, set status to `stopped`. If the payload omitted a known reason, record `unresolved_uncertainty` rather than dropping the stop.

## BLOCKER — Focus handoff refuses the Story C independence search

Requirement: an unresolved important relationship generates a follow-up, and the convergence path can approve that action. Marking the four known articles as `consider` is not a reason to cancel a search for a source outside that set.

Snapshot: implementation `2c8133a`. Retested after importing that commit. On `8e3e6e5` the same test failed because every candidate was archived with `low_expected_value`. The new ranker no longer archives them. It still does not approve the search.

Reproduction:

```text
/Users/bradleyharaguchi/SearchHax/exploration/.venv/bin/python -m pytest qa/tests/test_focus_and_versions.py::test_focus_approves_the_story_c_independence_search --tb=short -p no:cacheprovider --override-ini=testpaths=qa/tests
```

The Story C run builds one open question, importance 0.9 and missing evidence 1.0, and one unused action whose utility is 0.9. The query contains `independent primary confirmation of the Lumenarc Dynamics Series D amount` and `LF-PR-2026-031`. `evaluate_with_focus` is called with that request. No network call is made.

Expected: `stop` is false and `approved_action.query` contains `LF-PR-2026-031`.

Actual: `stop` is true, `stop_reason` is `unresolved_uncertainty`, and `approved_action` is null. All four candidates are `consider` with reason `eligible evidence candidate (not verified truth)`. The rationale begins `Focus marked candidates for consideration and did not request another search.`

Location: `exploration/backend/focus_bridge.py` lines 85–99. The approval branch at lines 69–84 runs only when some passage is `investigate`. The `consider` branch sees the open question and returns a stop without reading `proposed_actions`.

Deterministic: yes. `python -m unittest test_focus_attention.py` from `focus/` passes 12 tests. Those tests do not cover this handoff.

Suggested correction: when a pending action's utility is at least `budget.min_utility`, approve that action even if the current pages are only `consider`. Those pages are the shared-origin set. The follow-up exists to look outside it.

The fallback path is separate and still runs this follow-up. `run_story_c` with a down controller records `decision_source=fallback` and keeps the independence question. This blocker is the focus handoff, not that fallback.

## Earlier snapshot

The `8e3e6e5` offline suite aside from the test above had no blocking failures.

Command: `/Users/bradleyharaguchi/SearchHax/exploration/.venv/bin/python -m pytest exploration/tests qa/tests -m "not integration" -q --tb=line -p no:cacheprovider --override-ini=testpaths=`

Result: 53 passed, 2 live tests deselected, exit status 0. `python -m unittest test_focus_attention.py` from `focus/` : 5 passed. No Telem, Tavily, or LLM call was made.

The entity-save crash, duplicate controller query, gap-ranking miss, and inconsistent Story A rationale from `edf9e32` stay closed. No new blocker showed up in the focus handoff (`72dfbe1`, `0c04abe`, `8e3e6e5`).

Earlier findings:

Current release findings below were for commit `c81ea8e`. The entity-save crash and the missing-key demo rationale from `edf9e32` were closed before `ec31c60`. The duplicate-query and gap-ranking failures were open at `c81ea8e` and closed by `ec31c60`. The six Story A rows are two facts on three pages.

Snapshot: `edf9e32` (`feat/exploration`, "Record the exploration investigation milestone").

QA command: `/Users/bradleyharaguchi/SearchHax/exploration/.venv/bin/python -m pytest qa/tests -q --tb=line -p no:cacheprovider --override-ini=testpaths=qa/tests`

Result: 4 failed, 13 passed, exit status 1. No live Telem or Tavily call was made.

## BLOCKER — Follow-up save crashes when an entity id already exists

Requirement: structured extraction failures and later investigation steps must not crash the investigation. A second document that names an entity already in the graph must merge.

Reproduction:

```text
qa/tests/test_evidence_and_loop.py::test_repeated_entity_on_follow_up_does_not_crash
```

Two fetched pages both contain `NVIDIA invested $2 billion in CoreWeave.` The mocked extractor returns the same NVIDIA and CoreWeave entities for each page. The first step saves. The second step raises.

Expected: the follow-up is saved, and `NVIDIA` occurs once in the entity list.

Actual: `sqlite3.IntegrityError: UNIQUE constraint failed: entities.investigation_id, entities.id`.

Location: `exploration/backend/orchestrator.py` line 494 appends entities with `export.entities.extend` and does not drop ids already on the export. `exploration/backend/database.py` line 342 inserts every row. Entity ids come from `stable_id("ent", type, name)` in `exploration/backend/extraction.py` and are shared across documents.

Deterministic: yes.

Suggested correction: upsert entities by id before `replace_graph_rows`, or skip ids that are already stored for that investigation.

## BLOCKER — An already executed query is searched again

Requirement: duplicate follow-up queries are avoided, and the hard search budget is not spent twice on the same query.

Reproduction:

```text
qa/tests/test_evidence_and_loop.py::test_duplicate_controller_query_is_not_executed
```

The first step searches `alpha beta gamma delta`. The controller then approves that same string with `stop: false` and a rationale. The second step calls the provider again.

Expected: the repeated query is not sent. The recorded decision stays on the controller, and `searches_used` does not increase for that repeat.

Actual: the provider is called twice with `['alpha beta gamma delta', 'alpha beta gamma delta']`.

Location: `exploration/backend/orchestrator.py` lines 327–331 execute `decision.approved_action.query` without checking `search_queries`. `generate_actions` in `exploration/backend/planner.py` skips duplicates, but the controller path does not.

Deterministic: yes.

Suggested correction: if the approved query is already in search history, do not call `retrieval.search`. Keep `decision_source` as `convergence` and record that the action was already executed.

## BLOCKER — Committed Story A demo record contradicts itself

Requirement: Story A works from retrieved evidence, and no fabricated citation or metric is presented. A missing key must not be reported when extraction actually ran.

Reproduction: read `demo/evaluation.json` in commit `edf9e32`.

```text
qa/tests/test_evidence_and_loop.py::test_committed_story_a_record_is_internally_consistent
```

Expected: a recorded live run either extracts supported relationships from the fetched pages, or its rationale matches the real blocker. With `llm_configured: true` and `llm_calls: 5`, the rationale does not say the key is missing.

Actual:

- `story_a.blocker` is `LLM extraction failed: ReadTimeout`
- `story_a.llm_configured` is true and `usage.llm_calls` is 5
- `story_a.decision_rationale` says live extraction is blocked because no LLM key is configured
- `story_a.relationships` is `[]`
- `reports` for Story A repeats `latency_ms: 0` and `supported_relationships: 0`

Location: `demo/evaluation.json` lines 4–19 and the Story A report at lines 100–124. The current stop path at `exploration/backend/orchestrator.py` lines 296–298 stores `investigation.blocker` instead of that missing-key sentence, so this file does not match the code in the same commit.

Deterministic: yes for the committed file. This QA pass did not repeat the live search.

Suggested correction: regenerate `demo/evaluation.json` from the current code. Keep the ReadTimeout blocker if that is what the run did. Remove the missing-key rationale. Do not fill relationships that were not extracted. A Story A demo still needs a later run whose stored quotations support the NVIDIA relationships.

## HIGH — Unresolved gaps do not change which page is fetched

Requirement: unresolved graph gaps influence passage ranking.

Reproduction:

```text
qa/tests/test_evidence_and_loop.py::test_unresolved_gap_changes_which_page_is_fetched
```

One fetch slot remains. The follow-up returns `https://example.com/query-only` (snippet `alpha beta`, query overlap only) and `https://example.com/gap` (snippet `zeta quantum lattice`, the open gap). `score_passage` ranks the gap page higher when the gap list is passed. The fetch receives the query-only URL.

Expected: the fetched URL is `https://example.com/gap`.

Actual: the fetched URL is `https://example.com/query-only`.

Location: `exploration/backend/orchestrator.py` line 426 calls `score_passage` with the gap list set to `None`.

Deterministic: yes.

Suggested correction: pass the open question texts into `score_passage` when ranking snippets for fetch.
