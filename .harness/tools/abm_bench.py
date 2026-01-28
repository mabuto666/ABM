import argparse
import json
import subprocess
import sys
from pathlib import Path
from itertools import product

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import abm as abm_mod
    from util import json_write
else:
    from . import abm as abm_mod
    from .util import json_write


RUN_RECEIPTS_DIR = Path("receipts/RUN")
BENCH_DIR = Path("benchmarks")
RESULTS_PATH = Path("artifacts/abm/benchmarks/results.json")
LIMITS_DIR = Path("artifacts/abm/benchmarks/limits")


def load_benchmarks(path):
    specs = []
    for file_path in sorted(path.glob("*.json")):
        data = json.loads(file_path.read_text(encoding="utf-8"))
        specs.append(data)
    return specs


def expand_parameters(parameters):
    keys = sorted(parameters.keys())
    values = []
    for key in keys:
        val = parameters[key]
        if not isinstance(val, list):
            raise ValueError(f"parameters[{key}] must be list")
        values.append(val)
    for combo in product(*values):
        yield dict(zip(keys, combo))


def latest_run_done():
    if not RUN_RECEIPTS_DIR.exists():
        return None
    latest = None
    latest_ts = ""
    for path in RUN_RECEIPTS_DIR.glob("*.json"):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("kind") != "RUN_DONE":
            continue
        ts = payload.get("timestamp_utc", "")
        if ts >= latest_ts:
            latest_ts = ts
            latest = payload
    return latest


def run_ralph():
    result = subprocess.run(
        [sys.executable, ".harness/tools/ralph.py", "--loop"],
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"ralph run failed: {result.stdout.strip()} {result.stderr.strip()}".strip()
        )
    receipt = latest_run_done()
    if not receipt:
        raise RuntimeError("missing RUN_DONE receipt")
    return receipt


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--benchmarks", default=str(BENCH_DIR))
    parser.add_argument("--results", default=str(RESULTS_PATH))
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()

    benchmarks = load_benchmarks(Path(args.benchmarks))
    results = []

    for spec in benchmarks:
        benchmark_id = spec.get("benchmark_id")
        stress_axis = spec.get("stress_axis")
        parameters = spec.get("parameters", {})
        for param_set in expand_parameters(parameters):
            receipt = None
            if args.execute:
                receipt = run_ralph()
                abm_mod.write_aggregates()
            else:
                receipt = latest_run_done()
            aggregates = json.loads(Path(abm_mod.AGGREGATES_PATH).read_text(encoding="utf-8")) if abm_mod.AGGREGATES_PATH.exists() else {}
            indicators = abm_mod.compute_scaling_indicators(aggregates).get(
                receipt.get("run_id") if receipt else "", {}
            )
            limits = abm_mod.classify_limits({receipt.get("run_id") if receipt else "": indicators}).get(
                receipt.get("run_id") if receipt else "", {}
            )
            if receipt:
                LIMITS_DIR.mkdir(parents=True, exist_ok=True)
                limit_path = LIMITS_DIR / f"{receipt['run_id']}.json"
                json_write(limit_path, limits)
            results.append(
                {
                    "benchmark_id": benchmark_id,
                    "stress_axis": stress_axis,
                    "parameters": param_set,
                    "run_id": receipt.get("run_id") if receipt else None,
                    "dispatch_hash": receipt.get("dispatch_hash") if receipt else None,
                    "head": receipt.get("head") if receipt else None,
                    "indicators": indicators,
                    "limit": limits.get("limit") if limits else None,
                }
            )

    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    json_write(Path(args.results), {"results": results})
    print(str(args.results))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
