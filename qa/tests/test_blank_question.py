"""A blank question is not stored as an investigation."""

from __future__ import annotations

from fastapi.testclient import TestClient

from exploration.backend.main import create_app


def test_blank_question_is_rejected(tmp_path):
    app = create_app(tmp_path / "api.sqlite")
    client = TestClient(app)
    created = client.post("/api/exploration/investigations", json={"question": " "})
    assert created.status_code == 422, created.text
    listed = client.get("/api/exploration/investigations/does-not-exist")
    assert listed.status_code == 404
