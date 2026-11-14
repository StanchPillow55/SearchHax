import unittest

from answer_composer import AnswerGenerationError, compose_answer
from focus_attention import FocusAttentionModel, Passage


class AnswerComposerTests(unittest.TestCase):
    def setUp(self):
        model = FocusAttentionModel("why is electric vehicle demand weakening")
        self.decisions = model.rank([
            Passage("price", "High prices and interest rates can reduce EV demand.",
                    "https://example.com/price", title="EV affordability"),
            Passage("space", "A distant galaxy was observed by a telescope.",
                    "https://example.com/space", title="Space news"),
        ])

    def test_generates_only_from_considered_sources_and_appends_references(self):
        def fake_transport(payload):
            self.assertIn("[S1]", payload["prompt"])
            self.assertNotIn("Space news", payload["prompt"])
            return {"output_text": "EV demand may weaken because of affordability [S1]."}

        result = compose_answer("why is electric vehicle demand weakening", self.decisions,
                                transport=fake_transport)
        self.assertEqual(result.cited_source_ids, ("S1",))
        self.assertIn("https://example.com/price", result.markdown)

    def test_unknown_citations_are_rejected(self):
        with self.assertRaises(AnswerGenerationError):
            compose_answer("why", self.decisions,
                           transport=lambda payload: {"output_text": "Answer [S99]"})

    def test_missing_citation_is_rejected(self):
        with self.assertRaises(AnswerGenerationError):
            compose_answer("why", self.decisions,
                           transport=lambda payload: {"output_text": "Uncited answer"})

    def test_gemini_response_shape_is_supported(self):
        result = compose_answer(
            "why is electric vehicle demand weakening", self.decisions,
            provider="gemini",
            transport=lambda payload: {"candidates": [{"content": {"parts": [
                {"text": "Affordability is a factor [S1]."}
            ]}}]},
        )
        self.assertEqual(result.cited_source_ids, ("S1",))

    def test_local_openai_compatible_response_shape_is_supported(self):
        result = compose_answer(
            "why is electric vehicle demand weakening", self.decisions,
            provider="local",
            transport=lambda payload: {"choices": [{"message": {
                "content": "Affordability is a factor [S1]."
            }}]},
        )
        self.assertEqual(result.cited_source_ids, ("S1",))

    def test_non_strict_mode_preserves_uncited_answer(self):
        result = compose_answer(
            "why is electric vehicle demand weakening", self.decisions,
            provider="local", strict_citations=False,
            transport=lambda payload: {"choices": [{"message": {
                "content": "The local model's exact answer without references."
            }}]},
        )
        self.assertIn("exact answer without references", result.markdown)
        self.assertEqual(result.cited_source_ids, ())

    def test_normalizes_local_model_numeric_and_url_citations(self):
        result = compose_answer(
            "why is electric vehicle demand weakening", self.decisions,
            provider="local", strict_citations=False,
            transport=lambda payload: {"choices": [{"message": {
                "content": "Affordability is a factor [1]. More detail: https://example.com/price"
            }}]},
        )
        self.assertEqual(result.cited_source_ids, ("S1",))
        self.assertIn("[S1]", result.markdown)
        self.assertIn("https://example.com/price", result.markdown)


if __name__ == "__main__":
    unittest.main()
