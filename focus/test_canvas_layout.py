import unittest

from canvas_layout import collapse_evidence


def _evidence(node_id, claim, document_id):
    return {
        "id": node_id,
        "type": "evidence",
        "label": claim,
        "epistemic_status": "supported",
        "payload": {"claim_text": claim, "document_id": document_id, "passage": f"passage {node_id}"},
    }


class CollapseEvidenceTests(unittest.TestCase):
    def test_repeated_claims_collapse_without_dropping_passages(self):
        nodes = [
            {"id": "extract", "type": "extraction", "label": "Extraction"},
            _evidence("a", "Harbor raised a round", "doc-a"),
            _evidence("b", "Harbor raised a round", "doc-b"),
            {"id": "stop", "type": "convergence", "label": "Unresolved stop", "epistemic_status": "unresolved"},
        ]
        edges = [
            {"id": "e1", "source": "extract", "target": "a", "kind": "produced"},
            {"id": "e2", "source": "extract", "target": "b", "kind": "produced"},
            {"id": "e3", "source": "extract", "target": "stop", "kind": "sequence"},
        ]
        visible, collapsed = collapse_evidence(nodes, edges, set())
        group = next(node for node in visible if node["type"] == "evidence_group")
        self.assertEqual(group["payload"]["count"], 2)
        self.assertEqual(
            [member["payload"]["passage"] for member in group["payload"]["members"]],
            ["passage a", "passage b"],
        )
        self.assertNotIn("a", {node["id"] for node in visible})
        self.assertTrue(any(edge["target"] == group["id"] for edge in collapsed))
        self.assertTrue(any(edge["target"] == "stop" for edge in collapsed))

    def test_expanded_group_restores_every_member(self):
        nodes = [
            _evidence("a", "Same claim", "doc-a"),
            _evidence("b", "Same claim", "doc-b"),
        ]
        visible, _edges = collapse_evidence(nodes, [], {"claim:same claim"})
        self.assertEqual([node["id"] for node in visible], ["a", "b"])

    def test_distinct_claims_stay_separate(self):
        nodes = [
            _evidence("a", "First claim", "doc-a"),
            _evidence("b", "Second claim", "doc-b"),
        ]
        visible, _edges = collapse_evidence(nodes, [], set())
        self.assertEqual([node["type"] for node in visible], ["evidence", "evidence"])


if __name__ == "__main__":
    unittest.main()
