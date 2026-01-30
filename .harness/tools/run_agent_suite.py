import argparse
import hashlib
import json
import random
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import util as util_mod
else:
    from . import util as util_mod


RUNS_ROOT = Path("artifacts/abm_runs")
SUITES_ROOT = Path("artifacts/abm_suites")


def find_repo_root(start: Path) -> Optional[Path]:
    current = start.resolve()
    while True:
        if (current / ".harness").is_dir() and (current / "README.md").is_file():
            return current
        if current.parent == current:
            return None
        current = current.parent


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def ensure_suite_id(suite_id: str, scenarios: List[str], runs: int, seed: Optional[int]) -> str:
    if suite_id:
        return suite_id
    deterministic_time = util_mod.now_iso()
    if deterministic_time:
        base = f"{deterministic_time}|{','.join(scenarios)}|{runs}"
        suffix = hashlib.sha256(base.encode("utf-8")).hexdigest()[:8]
        return f"{deterministic_time}-{suffix}"
    rng = random.Random(seed) if seed is not None else random.SystemRandom()
    return "suite-" + "".join(rng.choice("0123456789abcdef") for _ in range(8))


def load_latest_run_id() -> str:
    latest = RUNS_ROOT / "LATEST"
    if latest.exists():
        return latest.read_text(encoding="utf-8").strip()
    return ""


def summarize_aggregates(aggregates: Dict[str, Any]) -> Dict[str, Any]:
    errors_total = sum(aggregates.get("errors_by_class", {}).values())
    retries_total = sum(aggregates.get("retries_by_class", {}).values())
    budgets = aggregates.get("budgets", {})
    tokens = budgets.get("tokens", {})
    if tokens.get("estimated") and tokens.get("tokens_est_total", 0):
        tokens_total = int(tokens.get("tokens_est_total", 0))
        tokens_estimated = True
    else:
        tokens_total = int(tokens.get("tokens_total", 0))
        tokens_estimated = False
    return {
        "total_ms": float(aggregates.get("total_ms", 0.0)),
        "errors_total": int(errors_total),
        "retries_total": int(retries_total),
        "tokens_total": tokens_total,
        "tokens_estimated": bool(tokens_estimated),
        "cost_total_usd": float(budgets.get("cost_total_usd", 0.0)),
    }


def percentile(values: List[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = int((pct / 100.0) * (len(ordered) - 1))
    return float(ordered[idx])


def mean(values: List[float]) -> float:
    return float(sum(values) / len(values)) if values else 0.0


def build_rollup(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    totals = [row["total_ms"] for row in rows]
    tokens = [row["tokens_total"] for row in rows]
    costs = [row["cost_total_usd"] for row in rows]
    errors = [row["errors_total"] for row in rows]
    return {
        "p95_total_ms": percentile(totals, 95),
        "mean_total_ms": mean(totals),
        "mean_tokens_total": mean(tokens),
        "mean_cost_total_usd": mean(costs),
        "errors_total_min": min(errors) if errors else 0,
        "errors_total_mean": mean(errors),
        "errors_total_max": max(errors) if errors else 0,
    }


def write_summary(path: Path, suite_report: Dict[str, Any]) -> None:
    lines = ["# ABM Agent Suite Summary", ""]
    lines.append(f"Suite id: {suite_report.get('suite_id', '')}")
    lines.append(f"Runs: {suite_report.get('total_runs', 0)}")
    lines.append(f"Pass rate: {suite_report.get('pass_rate', 0.0):.2f}")
    lines.append("")
    lines.append("## Per-scenario rollups")
    per_scenario = suite_report.get("per_scenario", {})
    if per_scenario:
        for name in sorted(per_scenario.keys()):
            rollup = per_scenario[name]
            lines.append(f"- {name}: p95_total_ms={rollup.get('p95_total_ms', 0.0):.2f}")
    else:
        lines.append("- none")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def suite_gate(suite_report: Dict[str, Any], scenarios_contract: Dict[str, Any]) -> List[str]:
    suite_rules = scenarios_contract.get("suite") if isinstance(scenarios_contract, dict) else None
    if not isinstance(suite_rules, dict):
        return []
    reasons: List[str] = []
    min_pass_rate = suite_rules.get("min_pass_rate")
    if isinstance(min_pass_rate, (int, float)):
        if suite_report.get("pass_rate", 0.0) < min_pass_rate:
            reasons.append(f"pass_rate {suite_report.get('pass_rate', 0.0):.2f} < {min_pass_rate}")
    max_p95_total_ms = suite_rules.get("max_p95_total_ms")
    if isinstance(max_p95_total_ms, (int, float)):
        if suite_report.get("overall", {}).get("p95_total_ms", 0.0) > max_p95_total_ms:
            reasons.append(
                f"p95_total_ms {suite_report.get('overall', {}).get('p95_total_ms', 0.0):.2f} > {max_p95_total_ms}"
            )
    max_mean_cost = suite_rules.get("max_mean_cost_total_usd")
    if isinstance(max_mean_cost, (int, float)):
        if suite_report.get("overall", {}).get("mean_cost_total_usd", 0.0) > max_mean_cost:
            reasons.append(
                f"mean_cost_total_usd {suite_report.get('overall', {}).get('mean_cost_total_usd', 0.0):.6f} > {max_mean_cost}"
            )
    return reasons


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenarios", required=True, help="Comma-separated scenario list")
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--concurrency", type=int, default=1)
    parser.add_argument("--suite_id", default="")
    parser.add_argument("--seed", type=int, default=None)
    args = parser.parse_args()

    if args.concurrency != 1:
        print("ERROR: only --concurrency 1 is supported")
        return 1

    scenarios = [item.strip() for item in args.scenarios.split(",") if item.strip()]
    scenarios = sorted(set(scenarios))
    if not scenarios:
        print("ERROR: no scenarios provided")
        return 1

    repo_root = find_repo_root(Path.cwd())
    if not repo_root:
        print("ERROR: could not locate repo root")
        return 1

    suite_id = ensure_suite_id(args.suite_id, scenarios, args.runs, args.seed)
    suite_dir = SUITES_ROOT / suite_id
    suite_runs: List[Dict[str, Any]] = []

    for scenario in scenarios:
        for run_index in range(1, args.runs + 1):
            result = subprocess.run(
                ["python3", ".harness/tools/run_agent_test.py", "--scenario", scenario],
                text=True,
                capture_output=True,
                cwd=repo_root,
            )
            run_id = load_latest_run_id()
            if not run_id:
                print("ERROR: missing artifacts/abm_runs/LATEST after run")
                return 1
            aggregates_path = RUNS_ROOT / run_id / "aggregates.json"
            if not aggregates_path.exists():
                print(f"ERROR: missing aggregates {aggregates_path}")
                return 1
            aggregates = load_json(aggregates_path)
            summary = summarize_aggregates(aggregates)
            suite_runs.append(
                {
                    "index": run_index,
                    "scenario": scenario,
                    "run_id": run_id,
                    "return_code": result.returncode,
                    "summary": summary,
                }
            )

    pass_count = sum(1 for row in suite_runs if row["return_code"] == 0)
    fail_count = len(suite_runs) - pass_count
    pass_rate = float(pass_count / len(suite_runs)) if suite_runs else 0.0

    per_scenario: Dict[str, Dict[str, Any]] = {}
    overall_rows: List[Dict[str, Any]] = []
    for scenario in scenarios:
        rows = [row["summary"] for row in suite_runs if row["scenario"] == scenario]
        per_scenario[scenario] = build_rollup(rows)
        overall_rows.extend(rows)

    overall = build_rollup(overall_rows)
    suite_report = {
        "suite_id": suite_id,
        "scenarios": scenarios,
        "runs_per_scenario": args.runs,
        "total_runs": len(suite_runs),
        "pass_count": pass_count,
        "fail_count": fail_count,
        "pass_rate": pass_rate,
        "per_scenario": per_scenario,
        "overall": overall,
    }

    suite_runs_payload = {
        "suite_id": suite_id,
        "scenarios": scenarios,
        "runs_per_scenario": args.runs,
        "runs": suite_runs,
    }

    write_json(suite_dir / "suite_runs.json", suite_runs_payload)
    write_json(suite_dir / "suite_report.json", suite_report)
    write_summary(suite_dir / "suite_summary.md", suite_report)

    scenarios_contract = load_json(repo_root / "contracts/abm_scenarios.json")
    reasons = suite_gate(suite_report, scenarios_contract)
    if reasons:
        print("abm_suite_gate: FAIL")
        for reason in sorted(reasons):
            print(f"- {reason}")
        return 1

    print("abm_suite_gate: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
