import json
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from util import now_iso, json_write
else:
    from .util import now_iso, json_write


EVENTS_PATH = Path("artifacts/abm/events.jsonl")
AGGREGATES_PATH = Path("artifacts/abm/aggregates.json")
EVENT_VERSION = "abm.event.v1"
AGGREGATES_VERSION = "abm.aggregates.v1"

MAX_CYCLES_WITHOUT_COMPLETE = 3
MAX_VERIFY_FAIL_STREAK = 3
MAX_CYCLES_PER_WORK_ORDER = 10


def _ensure_parent(path):
    path.parent.mkdir(parents=True, exist_ok=True)


def append_event(payload):
    _ensure_parent(EVENTS_PATH)
    with open(EVENTS_PATH, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n")


def load_events():
    if not EVENTS_PATH.exists():
        return []
    events = []
    for line in EVENTS_PATH.read_text(encoding="utf-8").splitlines():
        if line.strip():
            events.append(json.loads(line))
    return events


def _parse_cycle_id(cycle_id):
    if not isinstance(cycle_id, str):
        return 0
    if not cycle_id.startswith("cycle-"):
        return 0
    tail = cycle_id.split("-", 1)[1]
    return int(tail) if tail.isdigit() else 0


def next_cycle_id(run_id):
    max_id = 0
    for event in load_events():
        if event.get("run_id") == run_id:
            max_id = max(max_id, _parse_cycle_id(event.get("cycle_id")))
    return f"cycle-{max_id + 1:04d}"


def build_event(
    event_type,
    run_id,
    dispatch_hash,
    head,
    work_order_id,
    cycle_id,
    agent_id,
    detail=None,
):
    return {
        "event_version": EVENT_VERSION,
        "event_type": event_type,
        "timestamp_utc": now_iso(),
        "run_id": run_id,
        "dispatch_hash": dispatch_hash,
        "head": head,
        "work_order_id": work_order_id,
        "cycle_id": cycle_id,
        "agent_id": agent_id,
        "detail": detail or {},
    }


def compute_aggregates(events):
    event_counts = {}
    by_work_order = {}
    by_run = {}

    for event in events:
        event_type = event.get("event_type", "")
        event_counts[event_type] = event_counts.get(event_type, 0) + 1

        wo_id = event.get("work_order_id")
        run_id = event.get("run_id")
        cycle_id = event.get("cycle_id")
        detail = event.get("detail", {}) if isinstance(event.get("detail"), dict) else {}

        if isinstance(wo_id, str):
            wo = by_work_order.setdefault(
                wo_id,
                {
                    "cycle_count": 0,
                    "attempt_count": 0,
                    "verify_pass": 0,
                    "verify_fail": 0,
                    "state_transitions": 0,
                    "max_cycle_id": 0,
                },
            )
            if event_type == "cycle_start":
                wo["cycle_count"] += 1
            if event_type == "attempt_start":
                wo["attempt_count"] += 1
            if event_type == "verify_result":
                status = detail.get("status")
                if status == "pass":
                    wo["verify_pass"] += 1
                elif status == "fail":
                    wo["verify_fail"] += 1
            if event_type == "state_transition":
                wo["state_transitions"] += 1
            wo["max_cycle_id"] = max(wo["max_cycle_id"], _parse_cycle_id(cycle_id))

        if isinstance(run_id, str):
            run = by_run.setdefault(
                run_id,
                {
                    "cycle_count": 0,
                    "attempt_count": 0,
                    "verify_pass": 0,
                    "verify_fail": 0,
                    "state_transitions": 0,
                    "work_orders": set(),
                },
            )
            if event_type == "cycle_start":
                run["cycle_count"] += 1
            if event_type == "attempt_start":
                run["attempt_count"] += 1
            if event_type == "verify_result":
                status = detail.get("status")
                if status == "pass":
                    run["verify_pass"] += 1
                elif status == "fail":
                    run["verify_fail"] += 1
            if event_type == "state_transition":
                run["state_transitions"] += 1
            if isinstance(wo_id, str):
                run["work_orders"].add(wo_id)

    by_run_out = {}
    for run_id, data in by_run.items():
        data = dict(data)
        data["work_orders"] = sorted(data["work_orders"])
        by_run_out[run_id] = data

    aggregates = {
        "meta": {"version": AGGREGATES_VERSION},
        "event_counts": event_counts,
        "by_work_order": by_work_order,
        "by_run": by_run_out,
    }
    return aggregates


def write_aggregates():
    events = load_events()
    aggregates = compute_aggregates(events)
    _ensure_parent(AGGREGATES_PATH)
    json_write(AGGREGATES_PATH, aggregates)
    return aggregates
