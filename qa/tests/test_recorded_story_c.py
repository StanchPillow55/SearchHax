"""The committed profile file's Story C counts match a fresh offline run."""

from __future__ import annotations

import json
from pathlib import Path

from exploration.backend.baseline import run_baseline

RECORDED = Path(__file__).resolve().parents[2] / "demo" / "integrated_profile_evaluation.json"
SKIP = {"latency_ms", "notes", "cost_usd"}


def _down(*_args, **_kwargs):
    raise ConnectionError("convergence down")


def test_recorded_story_c_counts_match_a_fresh_offline_run(tmp_path):
    recorded = json.loads(RECORDED.read_text())
    for configuration in ("B0", "B3"):
        _export, report = run_baseline(
            story="C",
            configuration=configuration,
            db_path=tmp_path / f"{configuration}.sqlite",
            post=_down,
        )
        fresh = report.model_dump(mode="json")
        committed = next(
            item for item in recorded["reports"] if item["story"] == "C" and item["configuration"] == configuration
        )
        diffs = {
            key: (committed.get(key), fresh.get(key))
            for key in set(fresh) | set(committed)
            if key not in SKIP and committed.get(key) != fresh.get(key)
        }
        assert diffs == {}, diffs
        assert report.network_calls == 0
        assert report.llm_calls == 0
