import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

RUNS_ROOT = Path("artifacts/abm_runs")


def find_repo_root(start: Path) -> Optional[Path]:
    current = start.resolve()
    while True:
        if (current / ".harness").is_dir() and (current / "README.md").is_file():
            return current
        if current.parent == current:
            return None
        current = current.parent


def load_events(path: Path) -> List[Dict[str, Any]]:
    events: List[Dict[str, Any]] = []
    if not path.exists():
        return events
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        events.append(json.loads(line))
    return events


def _percentile(sorted_vals: List[float], pct: float) -> float:
    if not sorted_vals:
        return 0.0
    idx = int((pct / 100.0) * (len(sorted_vals) - 1))
    return float(sorted_vals[idx])


def aggregate_events(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    counts_by_kind: Dict[str, int] = {}
    counts_by_name: Dict[str, int] = {}
    counts_by_kind_name: Dict[str, Dict[str, int]] = {}
    durations_by_name: Dict[str, List[float]] = {}
    errors_by_class: Dict[str, int] = {}
    retries_by_class: Dict[str, int] = {}
    tokens_in = 0
    tokens_out = 0
    payload_chars_total = 0
    cost_total = 0.0

    for event in events:
        kind = event.get("kind", "")
        name = event.get("name", "")
        counts_by_kind[kind] = counts_by_kind.get(kind, 0) + 1
        counts_by_name[name] = counts_by_name.get(name, 0) + 1
        by_name = counts_by_kind_name.setdefault(kind, {})
        by_name[name] = by_name.get(name, 0) + 1

        ms = event.get("ms")
        if isinstance(ms, (int, float)):
            durations_by_name.setdefault(name, []).append(float(ms))

        meta = event.get("meta") if isinstance(event.get("meta"), dict) else {}
        if kind == "error":
            error_class = meta.get("error_class") or "unknown"
            errors_by_class[error_class] = errors_by_class.get(error_class, 0) + 1
        if kind == "retry":
            retry_class = meta.get("error_class") or "unknown"
            retries_by_class[retry_class] = retries_by_class.get(retry_class, 0) + 1

        tokens_in += int(meta.get("tokens_in", 0) or 0)
        tokens_out += int(meta.get("tokens_out", 0) or 0)
        payload_chars_total += int(
            meta.get("payload_chars", meta.get("text_bytes", 0)) or 0
        )
        try:
            cost_total += float(meta.get("cost_estimate_usd", 0.0) or 0.0)
        except (TypeError, ValueError):
            pass

    duration_stats: Dict[str, Dict[str, Any]] = {}
    total_ms = 0.0
    for name, values in durations_by_name.items():
        sorted_vals = sorted(values)
        total = sum(sorted_vals)
        total_ms += total
        duration_stats[name] = {
            "count": len(sorted_vals),
            "total_ms": total,
            "max_ms": max(sorted_vals) if sorted_vals else 0.0,
            "p50_ms": _percentile(sorted_vals, 50),
            "p90_ms": _percentile(sorted_vals, 90),
            "p95_ms": _percentile(sorted_vals, 95),
            "samples_ms": sorted_vals,
        }

    tokens_total = tokens_in + tokens_out
    tokens_est_total = int(math.ceil(payload_chars_total / 4.0)) if payload_chars_total else 0
    estimated = tokens_total == 0 and tokens_est_total > 0
    budgets_tokens_total = tokens_est_total if estimated else tokens_total

    aggregates = {
        "counts_by_kind": counts_by_kind,
        "counts_by_name": counts_by_name,
        "counts_by_kind_name": counts_by_kind_name,
        "durations_by_name": duration_stats,
        "errors_by_class": errors_by_class,
        "retries_by_class": retries_by_class,
        "tokens": {
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "tokens_total": tokens_total,
        },
        "budgets": {
            "tokens": {
                "tokens_in_total": int(tokens_in),
                "tokens_out_total": int(tokens_out),
                "tokens_total": int(budgets_tokens_total),
                "tokens_est_total": int(tokens_est_total),
                "estimated": bool(estimated),
            },
            "cost_total_usd": float(round(cost_total, 6)),
        },
        "total_ms": total_ms,
    }
    return aggregates


def write_summary(path: Path, aggregates: Dict[str, Any]) -> None:
    lines = []
    lines.append("# ABM Agent Test Summary")
    lines.append("")
    lines.append(f"Total ms: {aggregates.get('total_ms', 0.0):.2f}")
    lines.append("")
    lines.append("## Counts by kind")
    for kind in sorted(aggregates.get("counts_by_kind", {}).keys()):
        lines.append(f"- {kind}: {aggregates['counts_by_kind'][kind]}")
    lines.append("")
    lines.append("## Errors by class")
    errors = aggregates.get("errors_by_class", {})
    if errors:
        for name in sorted(errors.keys()):
            lines.append(f"- {name}: {errors[name]}")
    else:
        lines.append("- none")
    lines.append("")
    lines.append("## Retries by class")
    retries = aggregates.get("retries_by_class", {})
    if retries:
        for name in sorted(retries.keys()):
            lines.append(f"- {name}: {retries[name]}")
    else:
        lines.append("- none")
    lines.append("")
    lines.append("## Durations by name (p95 ms)")
    durations = aggregates.get("durations_by_name", {})
    if durations:
        for name in sorted(durations.keys()):
            stats = durations[name]
            lines.append(f"- {name}: {stats.get('p95_ms', 0.0):.2f}")
    else:
        lines.append("- none")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def aggregate_run(run_id: str, repo_root: Path, partial: bool = False) -> Path:
    run_dir = RUNS_ROOT / run_id
    events_path = run_dir / "events.jsonl"
    aggregates_path = run_dir / ("aggregates_partial.json" if partial else "aggregates.json")
    summary_path = run_dir / ("summary_partial.md" if partial else "summary.md")
    events = load_events(events_path)
    aggregates = aggregate_events(events)
    aggregates["run_id"] = run_id
    aggregates["event_count"] = len(events)
    aggregates_path.write_text(
        json.dumps(aggregates, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    write_summary(summary_path, aggregates)
    return aggregates_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run_id", default="", help="Run id (default: LATEST)")
    parser.add_argument("--partial", action="store_true", help="Write partial aggregates")
    args = parser.parse_args()

    repo_root = find_repo_root(Path.cwd())
    if not repo_root:
        print("ERROR: could not locate repo root")
        return 1

    if args.run_id:
        run_id = args.run_id
    else:
        latest = RUNS_ROOT / "LATEST"
        if not latest.exists():
            print("ERROR: missing artifacts/abm_runs/LATEST")
            return 1
        run_id = latest.read_text(encoding="utf-8").strip()

    aggregates_path = aggregate_run(run_id, repo_root, partial=args.partial)
    print(str(aggregates_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
