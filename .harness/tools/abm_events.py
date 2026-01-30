import json
import os
import sys
from pathlib import Path
from typing import Any, Dict

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import util as util_mod
else:
    from . import util as util_mod


RUNS_ROOT = Path("artifacts/abm_runs")


def ensure_run_dir(run_id: str) -> Path:
    path = RUNS_ROOT / run_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_latest_pointer(run_id: str) -> Path:
    RUNS_ROOT.mkdir(parents=True, exist_ok=True)
    pointer = RUNS_ROOT / "LATEST"
    pointer.write_text(f"{run_id}\n", encoding="utf-8")
    return pointer


def open_event_log(run_dir: Path):
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / "events.jsonl"
    return open(path, "a", encoding="utf-8")


def emit_event(fh, event: Dict[str, Any]) -> None:
    payload = dict(event)
    if "meta" not in payload or not isinstance(payload.get("meta"), dict):
        payload["meta"] = {}
    if "ts" not in payload or not payload.get("ts"):
        ts = util_mod.now_iso()
        if ts:
            payload["ts"] = ts
        else:
            payload.pop("ts", None)
    line = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    fh.write(line + "\n")
    fh.flush()
    if os.environ.get("ABM_STDOUT_EVENTS") == "1":
        print(f"ABM_EVENT {line}")
