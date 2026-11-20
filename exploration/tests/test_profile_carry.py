"""M8: a new investigation can carry the research profile stored on an existing one.

Offline: the profile investigation comes from the fixed local corpus (run_profile), and
creating an investigation is a local write. No search, fetch or model call runs.
"""

from fastapi.testclient import TestClient

from exploration.backend.main import create_app
from exploration.backend.orchestrator import Orchestrator

QUESTION = "Which packaging constraints limit AI accelerator supply next year?"


def _client(tmp_path):
    db = tmp_path / "profile-carry.sqlite"
    orchestrator = Orchestrator(db)
    profiled = orchestrator.run_profile()
    orchestrator.post = lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("convergence down"))
    plain = orchestrator.run_story_c()
    orchestrator.database.close()
    return TestClient(create_app(db)), profiled, plain.investigation.id


def test_new_investigation_copies_the_stored_profile_and_leaves_the_source_alone(tmp_path):
    client, profiled, _ = _client(tmp_path)
    source_id = profiled.investigation.id
    stored = profiled.profile or profiled.investigation.metadata.get("profile_snapshot")
    assert stored, "run_profile stores a research profile"
    before = client.get(f"/api/exploration/investigations/{source_id}").json()

    response = client.post(
        "/api/exploration/investigations",
        json={"question": QUESTION, "profile_from_investigation_id": source_id},
    )
    assert response.status_code == 200, response.text
    created = response.json()
    assert created["question"] == QUESTION
    assert created["status"] == "created"
    snapshot = created["metadata"]["profile_snapshot"]
    expected = stored if isinstance(stored, dict) else stored.model_dump(mode="json")
    assert snapshot == expected
    assert created["metadata"]["profile_source_investigation_id"] == source_id
    usage = created["usage"]
    assert not usage.get("search_calls") and not usage.get("network_calls") and not usage.get("llm_calls")

    # The knowledge view of the new investigation resolves the same profile.
    graph = client.get(f"/api/exploration/profile/knowledge-graph?investigation_id={created['id']}").json()
    assert graph["profile_id"] == snapshot["id"]
    # The source investigation is unchanged.
    assert client.get(f"/api/exploration/investigations/{source_id}").json() == before


def test_profile_source_must_exist_and_have_a_profile(tmp_path):
    client, _, plain_id = _client(tmp_path)
    missing = client.post(
        "/api/exploration/investigations",
        json={"question": QUESTION, "profile_from_investigation_id": "inv_does_not_exist"},
    )
    assert missing.status_code == 404
    no_profile = client.post(
        "/api/exploration/investigations",
        json={"question": QUESTION, "profile_from_investigation_id": plain_id},
    )
    assert no_profile.status_code == 422
    assert "no stored research profile" in no_profile.json()["detail"]
    listed = client.get("/api/exploration/investigations?limit=50").json()
    assert all(item["question"] != QUESTION for item in listed["items"]), "a refused request stores nothing"


def test_inline_profile_and_profile_source_cannot_be_combined(tmp_path):
    client, profiled, _ = _client(tmp_path)
    response = client.post(
        "/api/exploration/investigations",
        json={
            "question": QUESTION,
            "profile_from_investigation_id": profiled.investigation.id,
            "profile": {"id": "made_up", "interests": ["anything"]},
        },
    )
    assert response.status_code == 422


def test_same_idempotency_key_creates_one_profiled_investigation(tmp_path):
    client, profiled, _ = _client(tmp_path)
    body = {"question": QUESTION, "profile_from_investigation_id": profiled.investigation.id}
    first = client.post("/api/exploration/investigations", json=body, headers={"Idempotency-Key": "carry-1"})
    second = client.post("/api/exploration/investigations", json=body, headers={"Idempotency-Key": "carry-1"})
    assert first.status_code == second.status_code == 200
    assert first.json()["id"] == second.json()["id"]
