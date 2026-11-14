import json
from pathlib import Path

from fastapi.testclient import TestClient

from exploration.backend.main import create_app
from shared.contracts import CONTRACT_VERSION, ExplorationExport

ROOT = Path(__file__).resolve().parents[2]


def test_schema_and_example_payload_match_the_contract():
    schema = json.loads((ROOT / "shared" / "evidence.schema.json").read_text(encoding="utf-8"))
    definitions = json.dumps(schema["$defs"])
    for name in [
        "Investigation",
        "InvestigationBudget",
        "Document",
        "DocumentVersion",
        "EvidenceSpan",
        "Entity",
        "Claim",
        "Relationship",
        "EvidenceLink",
        "SourceProvenance",
        "UnresolvedQuestion",
        "EvidenceCandidate",
        "ConvergenceDecision",
        "InvestigationAction",
        "Checkpoint",
        "UsageMetrics",
    ]:
        assert name in definitions
    example = json.loads((ROOT / "shared" / "example_payload.json").read_text(encoding="utf-8"))
    parsed = ExplorationExport.model_validate(example)
    assert parsed.contract_version == CONTRACT_VERSION
    assert parsed.investigation.question
    assert parsed.investigation.budget.remaining_searches >= 0
    assert parsed.evidence_spans[0].attention is not None
    assert parsed.decision.decision_source == "fallback"


def test_story_c_endpoint(tmp_path):
    app = create_app(tmp_path / "api.sqlite")

    def down(*_args, **_kwargs):
        raise RuntimeError("convergence down")

    app.state.orchestrator.post = down
    client = TestClient(app)
    created = client.post("/api/exploration/investigations", json={"question": "What remains unresolved?"})
    assert created.status_code == 200
    investigation_id = created.json()["id"]
    missing = client.get("/api/exploration/investigations/does-not-exist")
    assert missing.status_code == 404
    story = client.post("/api/exploration/fixtures/story-c")
    assert story.status_code == 200
    body = story.json()
    assert body["origin_clusters"][0]["origin_id"] == "LF-PR-2026-031"
    assert body["contradictions"]
    assert body["investigation"]["decision_source"] == "fallback"
    fetched = client.get(f"/api/exploration/investigations/{body['investigation']['id']}/export")
    assert fetched.status_code == 200
    checkpoints = client.get(f"/api/exploration/investigations/{body['investigation']['id']}/checkpoints")
    assert checkpoints.status_code == 200
    assert len(checkpoints.json()) >= 2
    baseline = client.post("/api/exploration/baseline", json={"story": "C", "configuration": "B0"})
    assert baseline.status_code == 200
    report = baseline.json()
    assert report["ran"] is True
    assert report["contradiction_detections"] == 0
    assert report["shared_origin_detected"] is False
    assert report["network_calls"] == 0
    from exploration.backend.config import telem_configured

    if not telem_configured():
        blocked = client.post(f"/api/exploration/investigations/{investigation_id}/step")
        assert blocked.status_code == 200
        assert blocked.json()["investigation"]["status"] == "blocked"
        assert blocked.json()["investigation"]["blocker"] == "TELEM_API_KEY missing"
        assert blocked.json()["relationships"] == []
