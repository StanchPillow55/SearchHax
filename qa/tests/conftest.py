"""QA fixtures. These tests do not load .env and do not call live providers."""

from __future__ import annotations

import pytest

SECRET_ENV = (
    "TELEM_API_KEY",
    "TAVILY_API_KEY",
    "LLM_API_KEY",
    "OPENAI_API_KEY",
    "DRY_RUN",
    "CONVERGENCE_URL",
)


@pytest.fixture(autouse=True)
def isolate_provider_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in SECRET_ENV:
        monkeypatch.delenv(name, raising=False)
