"""The HTTP API keeps a research profile sent at creation."""

from __future__ import annotations

from fastapi.testclient import TestClient

from exploration.backend.main import create_app

PROFILE = {
    "id": "profile_ai_infrastructure",
    "interests": ["advanced packaging"],
    "unresolved_interests": ["advanced packaging"],
    "notes": "Static read-only test profile.",
}


def test_api_create_keeps_the_research_profile(tmp_path):
    app = create_app(tmp_path / "api.sqlite")
    client = TestClient(app)
    created = client.post(
        "/api/exploration/investigations",
        json={
            "question": "How do NVIDIA's investments, GPU infrastructure customers, and AI capacity expansion reinforce one another?",
            "profile": PROFILE,
        },
    )
    assert created.status_code == 200, created.text
    exported = client.get(f"/api/exploration/investigations/{created.json()['id']}")
    assert exported.status_code == 200, exported.text
    profile = exported.json().get("profile")
    assert profile is not None, profile
    assert profile["id"] == "profile_ai_infrastructure"
    assert profile["unresolved_interests"] == ["advanced packaging"]
