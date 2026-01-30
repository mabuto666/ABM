import argparse
import json
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


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _merge_thresholds(base: Dict[str, Any], overrides: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(base)
    for key, value in overrides.items():
        merged[key] = value
    return merged


def _merge_step_thresholds(*maps: Dict[str, Any]) -> Dict[str, Any]:
    merged: Dict[str, Any] = {}
    for mapping in maps:
        if not isinstance(mapping, dict):
            continue
        for key, value in mapping.items():
            merged[key] = value
    return merged


def _merge_artifacts(defaults: Dict[str, Any], overrides: Dict[str, Any]) -> Dict[str, List[str]]:
    required = list(defaults.get("required", [])) if isinstance(defaults, dict) else []
    forbidden = list(defaults.get("forbidden", [])) if isinstance(defaults, dict) else []
    if isinstance(overrides, dict):
        if "required" in overrides:
            required = list(overrides.get("required", []) or [])
        if "forbidden" in overrides:
            forbidden = list(overrides.get("forbidden", []) or [])
    return {"required": required, "forbidden": forbidden}


def evaluate(
    aggregates: Dict[str, Any],
    thresholds: Dict[str, Any],
    step_thresholds: Dict[str, Any],
    artifacts: Dict[str, List[str]],
    run_dir: Path,
) -> List[str]:
    reasons: List[str] = []
    total_ms = aggregates.get("total_ms", 0.0)
    total_errors = sum(aggregates.get("errors_by_class", {}).values())
    total_retries = sum(aggregates.get("retries_by_class", {}).values())
    tokens_total = aggregates.get("budgets", {}).get("tokens", {}).get("tokens_total", None)
    if tokens_total is None:
        tokens_total = aggregates.get("tokens", {}).get("tokens_total", 0)
    cost_total_usd = aggregates.get("budgets", {}).get("cost_total_usd", 0.0)

    max_total_ms = thresholds.get("max_total_ms")
    if isinstance(max_total_ms, (int, float)) and total_ms > max_total_ms:
        reasons.append(f"total_ms {total_ms:.2f} > {max_total_ms}")

    max_errors = thresholds.get("max_errors")
    if isinstance(max_errors, int) and total_errors > max_errors:
        reasons.append(f"errors {total_errors} > {max_errors}")

    max_retries = thresholds.get("max_retries")
    if isinstance(max_retries, int) and total_retries > max_retries:
        reasons.append(f"retries {total_retries} > {max_retries}")

    max_tokens_total = thresholds.get("max_tokens_total")
    if isinstance(max_tokens_total, int) and tokens_total > max_tokens_total:
        reasons.append(f"tokens_total {tokens_total} > {max_tokens_total}")

    max_cost_total = thresholds.get("max_cost_total_usd")
    if isinstance(max_cost_total, (int, float)) and cost_total_usd > max_cost_total:
        reasons.append(f"cost_total_usd {cost_total_usd:.6f} > {max_cost_total}")

    if isinstance(step_thresholds, dict):
        durations = aggregates.get("durations_by_name", {})
        for name in sorted(step_thresholds.keys()):
            limit = step_thresholds[name]
            if not isinstance(limit, (int, float)):
                continue
            p95 = durations.get(name, {}).get("p95_ms", 0.0)
            if p95 > limit:
                reasons.append(f"p95_ms {name} {p95:.2f} > {limit}")

    for artifact in sorted(artifacts.get("required", [])):
        if not (run_dir / artifact).exists():
            reasons.append(f"missing artifact {artifact}")

    for artifact in sorted(artifacts.get("forbidden", [])):
        if (run_dir / artifact).exists():
            reasons.append(f"forbidden artifact {artifact}")

    return reasons


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run_id", default="", help="Run id (default: LATEST)")
    parser.add_argument("--scenario", default="", help="Scenario name")
    parser.add_argument(
        "--thresholds",
        default="contracts/abm_thresholds.json",
        help="Threshold contract path",
    )
    parser.add_argument(
        "--scenarios_contract",
        default="contracts/abm_scenarios.json",
        help="Scenario contract path",
    )
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

    run_dir = RUNS_ROOT / run_id
    aggregates_path = run_dir / "aggregates.json"
    if not aggregates_path.exists():
        print(f"ERROR: missing aggregates {aggregates_path}")
        return 1

    thresholds_path = repo_root / args.thresholds
    if not thresholds_path.exists():
        print(f"ERROR: missing thresholds {thresholds_path}")
        return 1

    scenarios_path = repo_root / args.scenarios_contract
    if not scenarios_path.exists():
        print(f"ERROR: missing scenarios contract {scenarios_path}")
        return 1

    aggregates = load_json(aggregates_path)
    thresholds = load_json(thresholds_path)
    scenarios = load_json(scenarios_path)

    thresholds_defaults = thresholds if isinstance(thresholds, dict) else {}
    scenarios_defaults = scenarios.get("defaults", {}) if isinstance(scenarios, dict) else {}
    scenarios_thresholds = scenarios_defaults.get("thresholds", {})
    scenario_thresholds = {}
    scenario_steps = {}
    scenario_artifacts = {}
    if args.scenario:
        scenario = scenarios.get("scenarios", {}).get(args.scenario, {})
        if isinstance(scenario, dict):
            scenario_thresholds = scenario.get("thresholds", {}) or {}
            scenario_steps = scenario.get("steps", {}) or {}
            scenario_artifacts = scenario.get("artifacts", {}) or {}

    effective_thresholds = _merge_thresholds(thresholds_defaults, scenarios_thresholds)
    effective_thresholds = _merge_thresholds(effective_thresholds, scenario_thresholds)

    step_defaults = thresholds_defaults.get("max_p95_step_ms", {})
    scenario_step_defaults = scenarios_defaults.get("steps", {}).get("max_p95_step_ms", {})
    scenario_step_overrides = scenario_steps.get("max_p95_step_ms", {})
    step_thresholds = _merge_step_thresholds(step_defaults, scenario_step_defaults, scenario_step_overrides)

    artifacts_defaults = scenarios_defaults.get("artifacts", {}) if isinstance(scenarios_defaults, dict) else {}
    artifacts = _merge_artifacts(artifacts_defaults, scenario_artifacts)

    reasons = evaluate(aggregates, effective_thresholds, step_thresholds, artifacts, run_dir)

    if reasons:
        print("abm_gate: FAIL")
        for reason in sorted(reasons):
            print(f"- {reason}")
        return 1

    print("abm_gate: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
