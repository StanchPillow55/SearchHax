"""Benchmark native Ollama JSON-schema extraction. No Telem calls.

Cold is the first request after `ollama stop`. Warm is the immediate second pass.
Quotes are accepted only by the existing grounding function.
"""

from __future__ import annotations

import json
import time
import urllib.request
from pathlib import Path

from exploration.backend.extraction import relationships_from_llm_payload

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures" / "story_c"
HOST = "http://127.0.0.1:11434"

SCHEMA = {
    "type": "object",
    "properties": {
        "relationships": {
            "type": "array",
            "maxItems": 3,
            "items": {
                "type": "object",
                "properties": {
                    "subject": {"type": "string"},
                    "predicate": {"type": "string"},
                    "object": {"type": "string"},
                    "quote": {"type": "string"},
                    "kind": {"type": "string"},
                },
                "required": ["subject", "predicate", "object", "quote"],
            },
        }
    },
    "required": ["relationships"],
}

SYSTEM = (
    "Extract at most 3 subject-predicate-object relationships. "
    "quote must be copied exactly from the passage. "
    "If you cannot copy an exact span, return an empty relationships list. "
    "Do not invent amounts or names."
)


def passages() -> list[dict]:
    rows = []
    expected = {
        "original.md": "$400 million",
        "northline.md": "$400 million",
        "voltstreet.md": "$480 million",
        "harbor.md": "$400 million",
    }
    for name, amount in expected.items():
        text = (FIXTURE / name).read_text(encoding="utf-8")
        rows.append({"id": name, "text": text, "amount": amount})
    rows.append(
        {
            "id": "cedar.txt",
            "text": "Cedar Analytics reported that Harbor Light bought three turbines from Northwind Capital on May 2, 2026.",
            "amount": None,
            "must_include": "Harbor Light bought three turbines",
        }
    )
    return rows


def chat(model: str, passage: str, *, think: bool | None, timeout: float) -> dict:
    body = {
        "model": model,
        "stream": False,
        "format": SCHEMA,
        "options": {"temperature": 0, "num_predict": 220},
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": passage},
        ],
    }
    if think is not None:
        body["think"] = think
    data = json.dumps(body).encode()
    request = urllib.request.Request(
        HOST + "/api/chat",
        data=data,
        headers={"Content-Type": "application/json"},
    )
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode())
        wall = time.perf_counter() - started
        payload["_wall_s"] = round(wall, 3)
        payload["_timeout"] = False
        return payload
    except Exception as exc:
        return {"_timeout": True, "_error": type(exc).__name__, "_wall_s": round(time.perf_counter() - started, 3)}


def score(passage: dict, payload: dict) -> dict:
    if payload.get("_timeout"):
        return {
            "id": passage["id"],
            "timeout": True,
            "error": payload.get("_error"),
            "wall_s": payload.get("_wall_s"),
            "schema_valid": False,
            "quote_matches": 0,
            "emitted": 0,
            "invented": 0,
            "supported": 0,
            "expected_hit": False,
        }
    message = (payload.get("message") or {}).get("content") or ""
    try:
        parsed = json.loads(message)
        batch = relationships_from_llm_payload(
            parsed,
            passage["text"],
            document_id="bench",
            version_id="bench",
            version_hash="bench",
        )
        schema_valid = True
    except Exception as exc:
        return {
            "id": passage["id"],
            "timeout": False,
            "schema_valid": False,
            "parse_error": type(exc).__name__,
            "wall_s": payload.get("_wall_s"),
            "raw_preview": message[:240],
        }
    emitted = len(batch.relationships)
    supported = [rel for rel in batch.relationships if rel.status == "supported"]
    invented = emitted - len(supported)
    expected_hit = False
    for rel in supported:
        blob = f"{rel.subject_name} {rel.predicate} {rel.object_name}"
        amount = passage.get("amount")
        if amount and amount in blob:
            expected_hit = True
        if passage.get("must_include") and "Harbor Light" in blob and "turbines" in blob:
            expected_hit = True
    return {
        "id": passage["id"],
        "timeout": False,
        "schema_valid": schema_valid,
        "wall_s": payload.get("_wall_s"),
        "load_s": round((payload.get("load_duration") or 0) / 1e9, 3),
        "prompt_eval_s": round((payload.get("prompt_eval_duration") or 0) / 1e9, 3),
        "gen_s": round((payload.get("eval_duration") or 0) / 1e9, 3),
        "prompt_tokens": payload.get("prompt_eval_count"),
        "output_tokens": payload.get("eval_count"),
        "emitted": emitted,
        "quote_matches": len(supported),
        "invented": invented,
        "supported": len(supported),
        "expected_hit": expected_hit,
        "rows": [
            {"status": rel.status, "subject": rel.subject_name, "predicate": rel.predicate, "object": rel.object_name}
            for rel in batch.relationships
        ],
    }


def run_model(model: str, *, think: bool | None, timeout: float) -> dict:
    rows = passages()
    cold = [score(row, chat(model, row["text"], think=think, timeout=timeout)) for row in rows]
    warm = [score(row, chat(model, row["text"], think=think, timeout=timeout)) for row in rows]
    return {"model": model, "think": think, "timeout_s": timeout, "cold": cold, "warm": warm}


if __name__ == "__main__":
    import sys

    model = sys.argv[1]
    think = None
    if len(sys.argv) > 2:
        think = sys.argv[2].lower() == "true"
    timeout = float(sys.argv[3]) if len(sys.argv) > 3 else 60.0
    result = run_model(model, think=think, timeout=timeout)
    out = Path(sys.argv[4]) if len(sys.argv) > 4 else Path("demo") / f"llm_bench_{model.replace(':', '_')}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2) + "\n")
    print(out)
