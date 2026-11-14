"""Run Story C offline and, with --live, one bounded Story A investigation.

Writes demo/evaluation.json from the runs that actually finished.
Does not invent metrics. Does not write page bodies or API keys.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from exploration.backend.baseline import report_from_export, run_baseline
from exploration.backend.config import llm_api_key, telem_configured
from exploration.backend.orchestrator import STORY_A_QUESTION, Orchestrator


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="FrontierGraph exploration demo")
    parser.add_argument("--live", action="store_true", help="Run one Story A investigation against Telem.")
    parser.add_argument("--db", type=Path, default=REPO_ROOT / "exploration" / "data" / "demo.sqlite")
    args = parser.parse_args(argv)
    args.db.parent.mkdir(parents=True, exist_ok=True)

    reports = []
    story_c_dir = args.db.parent / "story-c.sqlite"
    _export_b0, report_b0 = run_baseline(story="C", configuration="B0", db_path=story_c_dir.with_name("story-c-b0.sqlite"))
    _export_b3, report_b3 = run_baseline(story="C", configuration="B3", db_path=story_c_dir.with_name("story-c-b3.sqlite"))
    reports.append(report_b0.model_dump(mode="json"))
    reports.append(report_b3.model_dump(mode="json"))
    print("Story C B3 stop:", _export_b3.investigation.stop_reason if _export_b3 else None)
    print("Story C contradictions:", report_b3.contradiction_detections)
    print("Story C shared origin:", report_b3.shared_origin_detected)
    print("Story C network calls:", report_b3.network_calls)

    story_a = {
        "ran": False,
        "blocker": None,
        "question": STORY_A_QUESTION,
    }
    if args.live:
        if not telem_configured():
            story_a["blocker"] = "TELEM_API_KEY missing"
            print("Story A skipped: TELEM_API_KEY missing")
        else:
            orchestrator = Orchestrator(args.db)
            investigation = orchestrator.create(STORY_A_QUESTION, mode="web")
            first = orchestrator.step(investigation.id)
            second = orchestrator.step(investigation.id)
            resume_stats = orchestrator.resume(investigation.id)
            report = report_from_export(second, story="A", configuration="B3")
            reports.append(report.model_dump(mode="json"))
            story_a = {
                "ran": True,
                "blocker": second.investigation.blocker,
                "question": second.investigation.question,
                "investigation_id": second.investigation.id,
                "stop_reason": second.investigation.stop_reason,
                "decision_source": second.investigation.decision_source,
                "decision_rationale": second.investigation.decision_rationale,
                "session_set": bool(second.investigation.session_id),
                "checkpoints": len(second.checkpoints),
                "resume": resume_stats,
                "llm_configured": bool(llm_api_key()),
                "relationships": [
                    {
                        "subject": rel.subject_name,
                        "predicate": rel.predicate,
                        "object": rel.object_name,
                        "status": rel.status,
                    }
                    for rel in second.relationships
                ],
                "open_questions": [question.text for question in second.unresolved_questions],
                "usage": second.investigation.usage.model_dump(mode="json"),
            }
            print("Story A stop:", second.investigation.stop_reason)
            print("Story A decision:", second.investigation.decision_source)
            print("Story A searches:", second.investigation.usage.search_calls)
            print("Story A fetches:", second.investigation.usage.urls_fetched)
            print("Story A llm:", second.investigation.usage.llm_calls)
            print("Story A supported:", report.supported_relationships)
            print("Story A resume network fetches:", resume_stats["network_fetches"])
            print("Initial docs:", len(first.documents), "final docs:", len(second.documents))
    else:
        story_a["blocker"] = "not requested; pass --live"

    payload = {
        "sample_note": "Counts are from the runs in this file. One investigation per configuration is not a statistical result.",
        "story_a": story_a,
        "reports": reports,
    }
    out = REPO_ROOT / "demo" / "evaluation.json"
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print("wrote", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
