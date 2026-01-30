import argparse
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

RUNS_ROOT = Path("artifacts/abm_runs")


def read_latest_run_id() -> Optional[str]:
    latest = RUNS_ROOT / "LATEST"
    if latest.exists():
        return latest.read_text(encoding="utf-8").strip()
    return None


def safe_load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def load_metrics(run_id: str) -> Dict[str, Any]:
    if not run_id:
        return {}
    run_dir = RUNS_ROOT / run_id
    partial = run_dir / "aggregates_partial.json"
    target = partial if partial.exists() else run_dir / "aggregates.json"
    return safe_load_json(target)


def extract_metrics(aggregates: Dict[str, Any]) -> Dict[str, Any]:
    errors_total = sum(aggregates.get("errors_by_class", {}).values())
    retries_total = sum(aggregates.get("retries_by_class", {}).values())
    budgets = aggregates.get("budgets", {})
    tokens = budgets.get("tokens", {})
    if tokens.get("estimated") and tokens.get("tokens_est_total", 0):
        tokens_label = "tokens_est_total"
        tokens_value = int(tokens.get("tokens_est_total", 0))
    else:
        tokens_label = "tokens_total"
        tokens_value = int(tokens.get("tokens_total", 0))
    return {
        "total_ms": float(aggregates.get("total_ms", 0.0)),
        "errors_total": int(errors_total),
        "retries_total": int(retries_total),
        tokens_label: tokens_value,
        "cost_total_usd": float(budgets.get("cost_total_usd", 0.0)),
    }


def tail_new_bytes(path: Path, position: int) -> Tuple[List[Dict[str, Any]], int]:
    if not path.exists():
        return [], position
    events: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as fh:
        fh.seek(position)
        for line in fh:
            if not line.strip():
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                break
        position = fh.tell()
    return events, position


def format_plain(
    counts: Dict[str, int],
    errors: List[str],
    metrics: Dict[str, Any],
    tick_delta: int,
    last_event: str,
) -> str:
    counts_str = ", ".join(f"{k}={counts[k]}" for k in sorted(counts.keys()))
    error_str = "; ".join(errors) if errors else "none"
    metrics_order = ["total_ms", "errors_total", "retries_total", "tokens_total", "tokens_est_total", "cost_total_usd"]
    metrics_parts = []
    for key in metrics_order:
        if key in metrics:
            value = metrics[key]
            if key == "total_ms":
                metrics_parts.append(f"{key}={value:.2f}")
            elif key == "cost_total_usd":
                metrics_parts.append(f"{key}={value:.6f}")
            else:
                metrics_parts.append(f"{key}={value}")
    metrics_str = ", ".join(metrics_parts)
    last_label = last_event or "none"
    return (
        f"rid={metrics.get('run_id', '')} tick+{tick_delta} last={last_label} "
        f"counts: {counts_str} | errors: {error_str} | {metrics_str}"
    )


def render_tui(
    counts: Dict[str, int],
    errors: List[str],
    metrics: Dict[str, Any],
    tick_delta: int,
    last_event: str,
) -> str:
    lines = []
    lines.append("ABM Agent Test Watcher")
    lines.append("")
    lines.append(f"Run id: {metrics.get('run_id', '')}")
    lines.append(f"Tick delta: {tick_delta}")
    lines.append(f"Last event: {last_event or 'none'}")
    lines.append("")
    lines.append("Metrics:")
    for key in ["total_ms", "errors_total", "retries_total", "tokens_total", "tokens_est_total", "cost_total_usd"]:
        if key not in metrics:
            continue
        value = metrics[key]
        if key == "total_ms":
            lines.append(f"  {key}: {value:.2f}")
        elif key == "cost_total_usd":
            lines.append(f"  {key}: {value:.6f}")
        else:
            lines.append(f"  {key}: {value}")
    lines.append("")
    lines.append("Counts by kind:")
    for key in sorted(counts.keys()):
        lines.append(f"  {key}: {counts[key]}")
    lines.append("")
    lines.append("Recent errors:")
    if errors:
        for err in errors:
            lines.append(f"  {err}")
    else:
        lines.append("  none")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run_id", default="", help="Run id (default: LATEST)")
    parser.add_argument("--interval", type=float, default=0.5)
    parser.add_argument("--plain", action="store_true")
    parser.add_argument("--tui", action="store_true")
    parser.add_argument("--errors", type=int, default=5)
    parser.add_argument("--ticks", type=int, default=0, help="Stop after N updates")
    args = parser.parse_args()

    pinned_run_id = args.run_id
    run_id = pinned_run_id or read_latest_run_id() or ""

    events_path = RUNS_ROOT / run_id / "events.jsonl" if run_id else None
    position = 0
    counts: Dict[str, int] = {}
    errors: List[str] = []
    ticks = 0

    while True:
        if not pinned_run_id:
            latest_run_id = read_latest_run_id() or ""
            if latest_run_id and latest_run_id != run_id:
                run_id = latest_run_id
                events_path = RUNS_ROOT / run_id / "events.jsonl"
                position = 0
                counts = {}
                errors = []

        tick_events = 0
        last_event = ""
        if events_path:
            new_events, position = tail_new_bytes(events_path, position)
            tick_events = len(new_events)
            if new_events:
                last = new_events[-1]
                last_event = f"{last.get('kind', '')}:{last.get('name', '')}"
            for event in new_events:
                kind = event.get("kind", "")
                counts[kind] = counts.get(kind, 0) + 1
                if kind == "error":
                    meta = event.get("meta") if isinstance(event.get("meta"), dict) else {}
                    error_class = meta.get("error_class") or "unknown"
                    name = event.get("name", "")
                    errors.append(f"{name}:{error_class}")
                    errors = errors[-args.errors :]

        aggregates = load_metrics(run_id)
        metrics = extract_metrics(aggregates)
        metrics["run_id"] = run_id
        output = (
            format_plain(counts, errors, metrics, tick_events, last_event)
            if args.plain or not args.tui
            else render_tui(counts, errors, metrics, tick_events, last_event)
        )
        if args.tui:
            print("\033[2J\033[H" + output, end="", flush=True)
        else:
            print(output, flush=True)

        ticks += 1
        if args.ticks and ticks >= args.ticks:
            break
        time.sleep(args.interval)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
