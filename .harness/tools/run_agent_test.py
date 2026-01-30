#!/usr/bin/env python3
"""
Atomic runner used by run_agent_suite.py.

Scenarios (minimal, deterministic):
- orc_verify_dod: runs ORC/ABM harness DoD verification
- orc_smoke: runs a minimal Ralph loop and then DoD (or just DoD if no work)

Contract:
- exit 0 on pass
- non-zero on fail
- writes an artifact JSON to artifacts/agent_tests/<run_id>.json

Env:
- HARNESS_NOW_ISO preferred for run_id determinism (falls back to UTC now)
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]


def now_iso() -> str:
    v = os.environ.get("HARNESS_NOW_ISO") or os.environ.get("ORC_NOW_ISO")
    if v:
        return v
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sh(cmd: list[str], timeout_s: int = 600) -> tuple[int, str]:
    p = subprocess.run(
        cmd,
        cwd=str(ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=timeout_s,
    )
    return p.returncode, p.stdout


def write_artifact(run_id: str, scenario: str, rc: int, out: str, extra: dict[str, Any] | None = None) -> None:
    d: dict[str, Any] = {
        "run_id": run_id,
        "scenario": scenario,
        "timestamp_utc": now_iso(),
        "return_code": rc,
        "stdout": out,
    }
    if extra:
        d.update(extra)
    out_dir = ROOT / "artifacts" / "agent_tests"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{run_id}-{scenario}.json").write_text(json.dumps(d, sort_keys=True) + "\n")


def verify_dod() -> tuple[int, str]:
    return sh([sys.executable, ".harness/tools/verify.py", "--check", "dod"])


def ralph_loop_once() -> tuple[int, str]:
    return sh([sys.executable, ".harness/tools/ralph.py", "--loop"], timeout_s=900)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", required=True, choices=["orc_verify_dod", "orc_smoke"])
    args = ap.parse_args()

    run_id = os.environ.get("SUITE_RUN_ID") or now_iso()

    if args.scenario == "orc_verify_dod":
        rc, out = verify_dod()
        write_artifact(run_id, args.scenario, rc, out)
        return rc

    if args.scenario == "orc_smoke":
        rc1, out1 = ralph_loop_once()
        rc2, out2 = verify_dod()
        rc = 0 if (rc1 == 0 and rc2 == 0) else (rc2 if rc2 != 0 else rc1)
        write_artifact(run_id, args.scenario, rc, out1 + "\n---\n" + out2, extra={"rc_ralph": rc1, "rc_dod": rc2})
        return rc

    raise AssertionError("unreachable")


if __name__ == "__main__":
    raise SystemExit(main())
