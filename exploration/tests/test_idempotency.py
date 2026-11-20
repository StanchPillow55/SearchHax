"""Duplicate-submission protection on write routes (M3). Offline; no provider calls."""

import threading

from fastapi.testclient import TestClient

from exploration.backend.main import create_app
from exploration.backend.orchestrator import Orchestrator
from exploration.tests.test_lantern_trace import _down


def _client(tmp_path):
    db = tmp_path / "idem.sqlite"
    orchestrator = Orchestrator(db)
    orchestrator.post = _down
    export = orchestrator.run_story_c()
    orchestrator.database.close()
    return TestClient(create_app(db)), export


def test_create_investigation_with_the_same_key_creates_one_row(tmp_path):
    client, _ = _client(tmp_path)
    total = client.get("/api/exploration/investigations").json()["total"]
    body = {"question": "What changed in GPU export rules in 2026?"}
    first = client.post("/api/exploration/investigations", json=body, headers={"Idempotency-Key": "k-1"})
    second = client.post("/api/exploration/investigations", json=body, headers={"Idempotency-Key": "k-1"})
    assert first.status_code == second.status_code == 200
    assert first.json()["id"] == second.json()["id"]
    assert first.json()["status"] == "created"
    assert client.get("/api/exploration/investigations").json()["total"] == total + 1


def test_reusing_a_key_for_a_different_request_is_refused(tmp_path):
    client, _ = _client(tmp_path)
    client.post("/api/exploration/investigations", json={"question": "A?"}, headers={"Idempotency-Key": "k-2"})
    other = client.post("/api/exploration/investigations", json={"question": "B?"}, headers={"Idempotency-Key": "k-2"})
    assert other.status_code == 409


def test_without_a_key_each_request_acts(tmp_path):
    client, _ = _client(tmp_path)
    a = client.post("/api/exploration/investigations", json={"question": "Same?"}).json()
    b = client.post("/api/exploration/investigations", json={"question": "Same?"}).json()
    assert a["id"] != b["id"]


def test_branch_with_the_same_key_creates_one_child(tmp_path):
    client, export = _client(tmp_path)
    inv = export.investigation.id
    body = {"from_checkpoint_id": export.checkpoints[-1].id, "objective": "Look at energy costs", "intervention_type": "fork"}
    a = client.post(f"/api/exploration/investigations/{inv}/branches", json=body, headers={"Idempotency-Key": "b-1"}).json()
    b = client.post(f"/api/exploration/investigations/{inv}/branches", json=body, headers={"Idempotency-Key": "b-1"}).json()
    assert a["child_investigation_id"] == b["child_investigation_id"]
    assert len(client.get(f"/api/exploration/investigations/{inv}/branches").json()) == 1


def test_a_failed_request_is_not_stored_so_a_retry_runs(tmp_path):
    client, export = _client(tmp_path)
    inv = export.investigation.id
    bad = {"from_checkpoint_id": "cp_missing", "intervention_type": "fork"}
    assert client.post(f"/api/exploration/investigations/{inv}/branches", json=bad, headers={"Idempotency-Key": "b-2"}).status_code == 404
    assert client.post(f"/api/exploration/investigations/{inv}/branches", json=bad, headers={"Idempotency-Key": "b-2"}).status_code == 404


def test_a_second_concurrent_step_is_refused(tmp_path):
    client, export = _client(tmp_path)
    app = client.app
    inv = client.post("/api/exploration/investigations", json={"question": "Concurrent?"}).json()["id"]
    started = threading.Event()
    release = threading.Event()
    calls = []

    def slow_step(investigation_id):
        calls.append(investigation_id)
        started.set()
        release.wait(5)
        return app.state.orchestrator.get(investigation_id)

    app.state.orchestrator.step = slow_step
    results = {}
    first = threading.Thread(target=lambda: results.setdefault("a", client.post(f"/api/exploration/investigations/{inv}/step")))
    first.start()
    assert started.wait(5)
    second = client.post(f"/api/exploration/investigations/{inv}/step")
    release.set()
    first.join(5)
    assert second.status_code == 409
    assert results["a"].status_code == 200
    assert calls == [inv]


def test_a_knowledge_correction_persists_and_is_not_duplicated_by_a_retry(tmp_path):
    db = tmp_path / "kn.sqlite"
    orchestrator = Orchestrator(db)
    orchestrator.post = _down
    export = orchestrator.run_profile()
    orchestrator.database.close()
    client = TestClient(create_app(db))
    inv = export.investigation.id
    graph = client.get(f"/api/exploration/profile/knowledge-graph?investigation_id={inv}").json()
    assert graph["profile_id"]
    encountered = next(n for n in graph["nodes"] if n["epistemic_state"] == "encountered")
    body = {
        "profile_id": graph["profile_id"],
        "investigation_id": inv,
        "subject": encountered["label"],
        "text": encountered["label"],
        "epistemic_state": "known",
        "basis": "user_confirmation",
    }
    for _ in range(2):
        assert client.post("/api/exploration/profile/knowledge-assertions", json=body, headers={"Idempotency-Key": "kn-1"}).status_code == 200
    # A fresh app on the same database (a restart) still has exactly one confirmation.
    reopened = TestClient(create_app(db)).get(f"/api/exploration/profile/knowledge-graph?investigation_id={inv}").json()
    mine = [n for n in reopened["nodes"] if n["confirmed"] and n["label"] == encountered["label"]]
    assert len(mine) == 1
    assert mine[0]["epistemic_state"] == "known"
    assert mine[0]["basis"] == "user_confirmation"
    # The encountered source itself is not promoted: it is still listed as encountered.
    assert any(n["id"] == encountered["id"] and n["epistemic_state"] == "encountered" for n in reopened["nodes"])


def test_a_later_correction_replaces_the_earlier_one(tmp_path):
    db = tmp_path / "kn2.sqlite"
    orchestrator = Orchestrator(db)
    orchestrator.post = _down
    export = orchestrator.run_profile()
    orchestrator.database.close()
    client = TestClient(create_app(db))
    inv = export.investigation.id
    graph = client.get(f"/api/exploration/profile/knowledge-graph?investigation_id={inv}").json()
    label = next(n for n in graph["nodes"] if n["epistemic_state"] == "frontier")["label"]
    base = {"profile_id": graph["profile_id"], "investigation_id": inv, "subject": label, "text": label, "basis": "user_confirmation"}
    client.post("/api/exploration/profile/knowledge-assertions", json={**base, "epistemic_state": "known"})
    after = client.post("/api/exploration/profile/knowledge-assertions", json={**base, "epistemic_state": "uncertain"}).json()
    mine = [n for n in after["nodes"] if n["basis"] == "user_confirmation" and n["label"] == label]
    assert [n["epistemic_state"] for n in mine] == ["uncertain"]
    assert any("superseded" in note for note in after["notes"])
