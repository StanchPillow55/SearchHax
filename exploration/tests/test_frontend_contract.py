"""Read-only API contract the React frontend depends on (frontend/src/api/schemas.ts).

If one of these assertions fails, the frontend's runtime validation would reject the
response, so the backend change needs a matching frontend change. Offline: Story C
fixture with the convergence controller stubbed out. No paid calls.
"""

from fastapi.testclient import TestClient

from exploration.backend.main import create_app
from exploration.backend.orchestrator import Orchestrator


def _down(*_args, **_kwargs):
    raise RuntimeError("convergence down")


def _client_with_story(tmp_path):
    db = tmp_path / "frontend-contract.sqlite"
    orchestrator = Orchestrator(db)
    orchestrator.post = _down
    export = orchestrator.run_story_c()
    orchestrator.database.close()
    return TestClient(create_app(db)), export.investigation.id


def _has(obj: dict, *keys: str) -> None:
    missing = [key for key in keys if key not in obj]
    assert not missing, f"missing {missing} in {sorted(obj)}"


def test_investigation_export_has_frontend_fields(tmp_path):
    client, inv_id = _client_with_story(tmp_path)
    response = client.get(f"/api/exploration/investigations/{inv_id}")
    assert response.status_code == 200
    body = response.json()
    _has(body, "contract_version", "investigation", "documents", "document_versions", "evidence_spans", "claims",
         "relationships", "evidence_links", "provenance", "unresolved_questions", "candidates", "contradictions", "checkpoints")
    inv = body["investigation"]
    _has(inv, "id", "question", "budget", "status", "stop_reason", "usage", "created_at", "updated_at", "metadata")
    assert inv["status"] in {"created", "running", "stopped", "blocked"}
    _has(inv["budget"], "max_searches", "max_fetched_urls", "max_llm_calls", "searches_used", "urls_fetched", "llm_calls_used")
    for doc in body["documents"]:
        _has(doc, "id", "canonical_url", "title")
    for span in body["evidence_spans"]:
        _has(span, "id", "version_id", "document_id", "text", "start", "end", "content_hash")
    for prov in body["provenance"]:
        _has(prov, "id", "document_id", "origin_kind")
        assert prov["origin_kind"] in {"original", "derivative", "unknown"}
    for claim in body["claims"]:
        assert claim["status"] in {"supported", "contradicted", "insufficient", "hypothesis"}
    assert body["checkpoints"], "Story C records checkpoints"
    for cp in body["checkpoints"]:
        _has(cp, "id", "investigation_id", "step", "state_json", "created_at", "summary")
        assert cp["investigation_id"] == inv_id


def test_checkpoint_policy_space_is_bounded_and_keyed(tmp_path):
    client, inv_id = _client_with_story(tmp_path)
    body = client.get(f"/api/exploration/investigations/{inv_id}").json()
    for cp in body["checkpoints"]:
        state = cp["state_json"]
        assert isinstance(state.get("snapshot", {}), dict)
        for point in state.get("policy_space", []):
            _has(point, "evidence_id", "document_id", "intent_alignment", "novelty", "unresolved_alignment", "action")
            for axis in ("intent_alignment", "novelty", "unresolved_alignment"):
                assert 0.0 <= point[axis] <= 1.0
            assert point["action"] in {"consider", "investigate", "archive"}


def test_trace_events_link_to_persisted_records(tmp_path):
    client, inv_id = _client_with_story(tmp_path)
    export = client.get(f"/api/exploration/investigations/{inv_id}").json()
    trace = client.get(f"/api/exploration/investigations/{inv_id}/trace").json()
    _has(trace, "investigation_id", "question", "incomplete", "events", "nodes", "edges", "parent_investigation_id", "from_checkpoint_id")
    assert trace["investigation_id"] == inv_id
    assert trace["question"] == export["investigation"]["question"]
    sequences = [event["sequence"] for event in trace["events"]]
    assert sequences == sorted(sequences)
    checkpoint_ids = {cp["id"] for cp in export["checkpoints"]}
    claim_ids = {claim["id"] for claim in export["claims"]}
    for event in trace["events"]:
        _has(event, "id", "investigation_id", "sequence", "stage", "created_at", "summary", "payload", "checkpoint_id")
        assert event["investigation_id"] == inv_id
        if event["stage"] == "checkpoint" and event["checkpoint_id"]:
            assert event["checkpoint_id"] in checkpoint_ids
        if event["stage"] == "extraction":
            for index, passage in enumerate(event["payload"].get("passages") or []):
                _has(passage, "claim_id", "document_id", "span_id", "status", "stances")
                assert passage["claim_id"] in claim_ids
                assert any(node["id"] == f"{event['id']}:p{index}" for node in trace["nodes"])


def test_branches_is_a_list_and_unknown_ids_are_404(tmp_path):
    client, inv_id = _client_with_story(tmp_path)
    assert isinstance(client.get(f"/api/exploration/investigations/{inv_id}/branches").json(), list)
    for path in ("", "/trace", "/branches"):
        assert client.get(f"/api/exploration/investigations/inv_does_not_exist{path}").status_code == 404


def test_list_investigations_is_read_only_and_newest_first(tmp_path):
    client, inv_id = _client_with_story(tmp_path)
    body = client.get("/api/exploration/investigations?limit=10").json()
    assert body["total"] >= 1 and body["limit"] == 10 and body["offset"] == 0
    row = next(item for item in body["items"] if item["id"] == inv_id)
    assert row["event_count"] > 0 and row["checkpoint_count"] > 0
    assert row["parent_investigation_id"] is None
    created = [item["created_at"] for item in body["items"]]
    assert created == sorted(created, reverse=True)
    assert client.get("/api/exploration/investigations?limit=0").status_code == 422


def test_saving_a_branch_through_the_api_leaves_the_parent_unchanged(tmp_path):
    client, inv_id = _client_with_story(tmp_path)
    before = client.get(f"/api/exploration/investigations/{inv_id}").json()
    trace_before = client.get(f"/api/exploration/investigations/{inv_id}/trace").json()
    checkpoint = before["checkpoints"][-1]["id"]
    response = client.post(
        f"/api/exploration/investigations/{inv_id}/branches",
        json={"from_checkpoint_id": checkpoint, "objective": "Challenge the amount", "intervention_type": "challenge_evidence", "constraints": {"max_searches": 1}},
    )
    assert response.status_code == 200
    branch = response.json()
    assert branch["parent_investigation_id"] == inv_id and branch["from_checkpoint_id"] == checkpoint
    after = client.get(f"/api/exploration/investigations/{inv_id}").json()
    trace_after = client.get(f"/api/exploration/investigations/{inv_id}/trace").json()
    assert after == before
    assert trace_after["events"] == trace_before["events"]
    child = client.get("/api/exploration/investigations?limit=50").json()["items"]
    row = next(item for item in child if item["id"] == branch["child_investigation_id"])
    assert row["parent_investigation_id"] == inv_id
    assert row["intervention_type"] == "challenge_evidence"
    assert row["from_checkpoint_id"] == checkpoint
    assert row["status"] in {"created", "stopped", "running", "blocked"}
    unknown = client.post(
        f"/api/exploration/investigations/{inv_id}/branches",
        json={"from_checkpoint_id": "cp_missing", "intervention_type": "fork"},
    )
    assert unknown.status_code == 404


def test_branch_attachments_are_validated_against_the_checkpoint_and_recorded_on_the_child(tmp_path):
    client, inv_id = _client_with_story(tmp_path)
    parent = client.get(f"/api/exploration/investigations/{inv_id}").json()
    cp = parent["checkpoints"][-1]
    snapshot = cp["state_json"]["snapshot"]
    claim = snapshot["claims"][0]
    doc = snapshot["documents"][0]
    response = client.post(
        f"/api/exploration/investigations/{inv_id}/branches",
        json={
            "from_checkpoint_id": cp["id"],
            "objective": "Find independent confirmation",
            "intervention_type": "fork",
            "attached_claim_ids": [claim["id"]],
            "attached_source_ids": [doc["id"]],
        },
    )
    assert response.status_code == 200
    child_id = response.json()["child_investigation_id"]
    trace = client.get(f"/api/exploration/investigations/{child_id}/trace").json()
    assert trace["parent_investigation_id"] == inv_id
    assert trace["from_checkpoint_id"] == cp["id"]
    assert trace["branch_objective"] == "Find independent confirmation"
    assert trace["attached_claims"] == [{"id": claim["id"], "text": claim["text"], "status": claim["status"]}]
    assert trace["attached_sources"] == [{"id": doc["id"], "title": doc["title"], "url": doc["canonical_url"]}]
    # The parent itself never gains attachment fields.
    parent_trace = client.get(f"/api/exploration/investigations/{inv_id}/trace").json()
    assert parent_trace["attached_claims"] == [] and parent_trace["attached_sources"] == []

    bad = client.post(
        f"/api/exploration/investigations/{inv_id}/branches",
        json={"from_checkpoint_id": cp["id"], "intervention_type": "fork", "attached_claim_ids": ["clm_not_recorded"]},
    )
    assert bad.status_code == 422
    assert client.get(f"/api/exploration/investigations/{inv_id}").json() == parent
