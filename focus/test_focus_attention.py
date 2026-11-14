import unittest
from datetime import date

from focus_attention import FocusAttentionModel, Passage, canonical_url


class FocusAttentionTests(unittest.TestCase):
    def setUp(self):
        self.model = FocusAttentionModel(
            "why is electric vehicle demand weakening",
            unresolved_questions=("are battery degradation and resale value affecting purchases",),
            domain_terms=("electric vehicle demand battery resale charging",),
            now=date(2026, 11, 14),
        )

    def test_canonical_url_removes_tracking_and_trailing_slash(self):
        self.assertEqual(
            canonical_url("HTTPS://Example.com/story/?utm_source=x&b=2"),
            "https://example.com/story?b=2",
        )

    def test_duplicate_urls_are_only_considered_once(self):
        passages = [
            Passage("a", "EV demand falls as battery resale value concerns grow", "https://example.com/story?utm_source=x"),
            Passage("b", "same story", "https://example.com/story"),
        ]
        self.assertEqual(len(self.model.rank(passages)), 1)

    def test_novel_relevant_evidence_is_investigated(self):
        decision = self.model.decide(Passage(
            "battery", "why electric vehicle demand is weakening: battery degradation and resale value affect purchases",
            "https://battery.example/report", providers=("tavily",), source_quality=0.9,
        ))
        self.assertEqual(decision.action, "investigate")
        self.assertGreater(decision.score.novelty, decision.score.redundancy)

    def test_unrelated_evidence_is_archived(self):
        decision = self.model.decide(Passage("chem", "new battery chemistry for grid storage", "https://x.example"))
        self.assertEqual(decision.action, "archive")

    def test_exploration_changes_policy_not_attention(self):
        passage = Passage("p", "electric vehicle demand and battery resale value", "https://x.example")
        focused = FocusAttentionModel(self.model.intent, exploration=0.0)
        exploratory = FocusAttentionModel(self.model.intent, exploration=1.0)
        self.assertEqual(focused.score(passage).attention, exploratory.score(passage).attention)
        self.assertLess(focused.novelty_threshold, exploratory.novelty_threshold)


if __name__ == "__main__":
    unittest.main()
