"""M11 deployment settings: database location, health probe and CORS origins. Offline."""

from fastapi.testclient import TestClient

from exploration.backend import config
from exploration.backend.main import LOCAL_ORIGINS, allowed_origins, create_app


def test_db_path_comes_from_the_environment_when_set(tmp_path, monkeypatch):
    target = tmp_path / "volume" / "exploration.sqlite"
    monkeypatch.setenv("SEARCHHAX_DB_PATH", str(target))
    assert config.default_db_path() == target
    monkeypatch.delenv("SEARCHHAX_DB_PATH")
    assert config.default_db_path() == config.EXPLORATION_ROOT / "data" / "exploration.sqlite"


def test_health_reports_presence_never_values(tmp_path, monkeypatch):
    monkeypatch.setenv("TELEM_API_KEY", "offline-test-placeholder-not-a-key")
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    client = TestClient(create_app(tmp_path / "health.sqlite"))
    body = client.get("/api/health").json()
    assert body["status"] == "ok" and body["database"] == "ok"
    assert body["search_configured"] is True and body["llm_configured"] is False
    assert "offline-test-placeholder" not in str(body)


def test_extra_origins_are_added_but_a_wildcard_is_refused(monkeypatch):
    monkeypatch.setenv("SEARCHHAX_ALLOWED_ORIGINS", "https://searchhax.internal.test, *, ")
    origins = allowed_origins()
    assert origins[: len(LOCAL_ORIGINS)] == LOCAL_ORIGINS
    assert "https://searchhax.internal.test" in origins
    assert "*" not in origins and "" not in origins
