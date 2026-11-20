"""The committed evidence schema matches the committed models."""

from __future__ import annotations

import json
from pathlib import Path

from shared.contracts import ExplorationExport

SCHEMA = Path(__file__).resolve().parents[2] / "shared" / "evidence.schema.json"


def test_committed_schema_includes_profile_and_knowledge_value():
    committed = json.loads(SCHEMA.read_text())
    live = ExplorationExport.model_json_schema()
    missing_defs = sorted(set(live["$defs"]) - set(committed["$defs"]))
    missing_root = sorted(set(live["properties"]) - set(committed["properties"]))
    missing_candidate = sorted(
        set(live["$defs"]["EvidenceCandidate"]["properties"])
        - set(committed["$defs"]["EvidenceCandidate"]["properties"])
    )
    assert (missing_defs, missing_root, missing_candidate) == ([], [], []), (
        missing_defs,
        missing_root,
        missing_candidate,
    )
