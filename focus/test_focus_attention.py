import unittest
from datetime import date
from focus_attention import FocusAttentionModel, Passage, canonical_url


class TinyEmbedder:
    """Deterministic fixture. encode() does not touch the network."""

    def encode(self, texts):
        out = []
        for text in texts:
            lower = text.lower()
            if "galax" in lower or "telescope" in lower:
                out.append((0.0, 0.0, 1.0))
            elif "battery" in lower or "resale" in lower or "longevity" in lower:
                out.append((0.85, 0.52, 0.0))
            else:
                out.append((1.0, 0.0, 0.0))
        return out


class FocusAttentionTests(unittest.TestCase):
    def setUp(self):
        self.model = FocusAttentionModel(
            "why is electric vehicle demand weakening",
            unresolved_questions=("are battery degradation and resale value affecting purchases",),
            domain_terms=("electric vehicle demand battery resale charging",),
            now=date(2026, 11, 14),
        )

    def test_canonical_url(self):
        self.assertEqual(
            canonical_url("HTTPS://Example.com/story/?utm_source=x&b=2"),
            "https://example.com/story?b=2",
        )

    def test_duplicate_url_and_provider_merge(self):
        passages = [
            Passage("a", "electric vehicle demand weakening", "https://x.example/story?utm_source=x", providers=("telem",)),
            Passage("b", "same story", "https://x.example/story", providers=("tavily",)),
        ]
        result = self.model.rank(passages)
        self.assertEqual(len(result), 1)
        self.assertEqual(set(result[0].passage.providers), {"telem", "tavily"})
        self.assertEqual(len(self.model.rank(passages)), 0)

    def test_novel_relevant_evidence_is_investigated(self):
        self.model.rank([Passage("seed", "why is electric vehicle demand weakening", "https://x.example/seed")])
        decision = self.model.decide(
            Passage(
                "battery",
                "electric vehicle demand battery resale",
                "https://battery.example/report",
                providers=("tavily",),
                source_quality=0.9,
            )
        )
        self.assertEqual(decision.action, "investigate")

    def test_relevant_long_search_snippet_clears_intent_floor(self):
        decision = self.model.decide(
            Passage(
                "search-result",
                "Automakers brace for EV demand decline following tax credit elimination. "
                "The report includes background, market context, and several unrelated details.",
                "https://example.com/ev-demand",
            )
        )
        self.assertGreaterEqual(decision.score.relevance, self.model.intent_floor)
        self.assertNotEqual(decision.action, "archive")

    def test_unrelated_evidence_is_archived(self):
        decision = self.model.decide(Passage("chem", "new battery chemistry for grid storage", "https://x.example"))
        self.assertEqual(decision.action, "archive")

    def test_exploration_changes_policy_not_attention(self):
        passage = Passage("p", "electric vehicle demand and battery resale value", "https://x.example")
        low = FocusAttentionModel(self.model.intent, exploration=0.0)
        high = FocusAttentionModel(self.model.intent, exploration=1.0)
        self.assertEqual(low.score(passage).attention, high.score(passage).attention)
        self.assertGreater(low.novelty_threshold, high.novelty_threshold)
        self.assertGreater(high.investigation_budget, low.investigation_budget)

    def test_identical_text_different_urls_deduplicated_sequentially(self):
        text = "why is electric vehicle demand weakening due to financing"
        result = self.model.rank(
            [Passage("a", text, "https://a.example"), Passage("b", text, "https://b.example")]
        )
        self.assertEqual(result[0].action, "consider")
        self.assertEqual(result[1].action, "archive")
        self.assertEqual(result[1].score.redundancy, 1.0)

    def test_semantic_embeddings_not_lexical_only(self):
        model = FocusAttentionModel("electric vehicle demand", embedder=TinyEmbedder())
        result = model.rank(
            [
                Passage("a", "vehicle price impact", "https://a.example"),
                Passage("b", "automobile affordability trends", "https://b.example"),
            ]
        )
        self.assertEqual(result[1].action, "archive")
        self.assertEqual(result[1].score.redundancy, 1.0)

    def test_unrelated_with_embeddings(self):
        model = FocusAttentionModel("electric vehicle demand", embedder=TinyEmbedder())
        self.assertEqual(
            model.decide(Passage("g", "galaxy telescope observations", "https://g.example")).action,
            "archive",
        )

    def test_stopping_after_stagnation(self):
        self.model.rank([Passage("a", "electric vehicle demand weakening", "https://a.example")])
        self.assertFalse(self.model.should_stop())
        self.model.rank([])
        self.model.rank([])
        self.assertTrue(self.model.should_stop())

    def test_invalid_embedding(self):
        class BadEmbedder:
            def encode(self, texts):
                return [(0, 0, 0)] * len(texts)

        with self.assertRaises(ValueError):
            FocusAttentionModel("test", embedder=BadEmbedder())

    def test_evidence_packet_excludes_unverified(self):
        self.model.rank([Passage("seed", "why is electric vehicle demand weakening", "https://a.example")])
        self.model.rank([Passage("novel", "electric vehicle demand battery resale", "https://b.example")])
        self.assertTrue(all(item["id"] != "novel" for item in self.model.evidence_packet()))


if __name__ == "__main__":
    unittest.main()


class ResearchLoopTests(unittest.TestCase):
    def test_follow_up_query_and_budget(self):
        from research_loop import run_research
        model = FocusAttentionModel('electric vehicle demand', exploration=1.0)
        calls = []
        def retrieve(query):
            calls.append(query)
            if len(calls) == 1:
                return [Passage('a','electric vehicle demand decreases', 'https://a.example'),
                        Passage('b','electric vehicle demand battery resale', 'https://b.example')]
            return [Passage('c','electric vehicle demand resale evidence', 'https://c.example')]
        result = run_research(model, retrieve, max_search_calls=2)
        self.assertLessEqual(result.search_calls, 2)
        self.assertEqual(result.search_calls, len(calls))
        self.assertGreaterEqual(result.accepted, 1)

    def test_query_plan_runs_multiple_explicit_searches(self):
        from research_loop import run_research
        model = FocusAttentionModel('electric vehicle demand', exploration=0.0)
        calls = []
        result = run_research(
            model, lambda query: calls.append(query) or [],
            max_search_calls=3, max_stagnant_batches=3,
            query_plan=('electric vehicle demand causes', 'electric vehicle demand counterevidence'),
        )
        self.assertEqual(result.search_calls, 3)
        self.assertEqual(calls, [
            'electric vehicle demand',
            'electric vehicle demand causes',
            'electric vehicle demand counterevidence',
        ])

    def test_normalized_provider_results(self):
        from retrieval_adapters import normalize_results
        data={'results':[{'title':'EV','content':'Vehicle pricing','url':'https://a.example'},
                         {'title':'Missing','content':'none'}]}
        results=normalize_results(data, 'tavily')
        self.assertEqual(len(results),1)
        self.assertEqual(results[0].providers,('tavily',))

    def test_normalized_telem_response(self):
        from retrieval_adapters import normalize_results
        data = {'preprocessor_runs': [
            {'preprocessor_name': 'brave', 'output_payload': {'results': [
                {'title': 'EV prices', 'summary': 'Prices remain high', 'url': 'https://a.example'}
            ]}},
            {'preprocessor_name': 'exa', 'output_payload': {'results': [
                {'title': 'Battery resale', 'url': 'https://b.example'}
            ]}},
        ]}
        results = normalize_results(data, 'telem')
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].providers, ('brave', 'telem'))
        self.assertEqual(results[1].text, 'Battery resale')

    def test_normalized_telem_fetch_response(self):
        from retrieval_adapters import _fetch_rows
        rows = _fetch_rows({'results': [
            {'url': 'https://example.com/a', 'content': '# Full page'},
            {'url': 'https://example.com/b', 'status': 'failed', 'error': 'paywall'},
        ]})
        self.assertEqual(rows[0]['content'], '# Full page')
        nested = _fetch_rows({'preprocessor_runs': [{
            'output_payload': {'fetched_results': [
                {'url': 'https://example.com/c', 'content': 'Nested page'}
            ]}
        }]})
        self.assertEqual(nested[0]['content'], 'Nested page')
