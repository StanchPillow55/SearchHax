"""Local exploration API. No authentication service. CORS is limited to localhost."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from shared.contracts import (
    BaselineReport,
    BaselineRequest,
    Checkpoint,
    CreateInvestigationRequest,
    ExplorationExport,
    Investigation,
)

from exploration.backend.baseline import run_baseline
from exploration.backend.config import default_db_path
from exploration.backend.orchestrator import Orchestrator

LOCAL_ORIGINS = [
    "http://localhost",
    "http://localhost:3000",
    "http://localhost:5173",
    "http://localhost:8000",
    "http://127.0.0.1",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:8000",
]


def create_app(db_path: str | Path | None = None) -> FastAPI:
    app = FastAPI(title="FrontierGraph Exploration", version="1.0.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=LOCAL_ORIGINS,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )
    app.state.orchestrator = Orchestrator(db_path or default_db_path())

    @app.post("/api/exploration/investigations", response_model=Investigation)
    def create_investigation(body: CreateInvestigationRequest) -> Investigation:
        return app.state.orchestrator.create(body.question, body.budget)

    @app.get("/api/exploration/investigations/{investigation_id}", response_model=ExplorationExport)
    def get_investigation(investigation_id: str) -> ExplorationExport:
        return _load(app, investigation_id)

    @app.post("/api/exploration/investigations/{investigation_id}/step", response_model=ExplorationExport)
    def step_investigation(investigation_id: str) -> ExplorationExport:
        _load(app, investigation_id)
        return app.state.orchestrator.step(investigation_id)

    @app.get("/api/exploration/investigations/{investigation_id}/graph", response_model=ExplorationExport)
    def get_graph(investigation_id: str) -> ExplorationExport:
        return _load(app, investigation_id)

    @app.get("/api/exploration/investigations/{investigation_id}/checkpoints", response_model=list[Checkpoint])
    def get_checkpoints(investigation_id: str) -> list[Checkpoint]:
        export = _load(app, investigation_id)
        return export.checkpoints

    @app.get("/api/exploration/investigations/{investigation_id}/export", response_model=ExplorationExport)
    def export_investigation(investigation_id: str) -> ExplorationExport:
        return _load(app, investigation_id)

    @app.post("/api/exploration/baseline", response_model=BaselineReport)
    def baseline(body: BaselineRequest) -> BaselineReport:
        _export, report = run_baseline(
            story=body.story,
            configuration=body.configuration,
            db_path=app.state.orchestrator.database.path.parent / f"baseline-{body.story}-{body.configuration}.sqlite",
            post=app.state.orchestrator.post,
        )
        return report

    @app.post("/api/exploration/fixtures/story-c", response_model=ExplorationExport)
    def story_c() -> ExplorationExport:
        return app.state.orchestrator.run_story_c()

    return app


def _load(app: FastAPI, investigation_id: str) -> ExplorationExport:
    try:
        return app.state.orchestrator.get(investigation_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="investigation not found") from exc


app = create_app()
