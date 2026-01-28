#!/usr/bin/env python3
"""
Export an ABM UI bundle (results.json, aggregates.json, events.jsonl) to a target folder.

Goal: make ABM_UI (and any other consumer UI) able to read a stable filesystem contract
without coupling UI logic into ABM core.

Usage:
  python3 tools/export_ui_bundle.py --out /path/to/ABM_UI/web/data
  python3 tools/export_ui_bundle.py --out /path/to/ABM_UI/web/data --prefer artifacts/abm
"""
from __future__ import annotations
import argparse
from pathlib import Path
import shutil
import sys

CANDIDATES = {
    "results.json": [
        "artifacts/abm/benchmarks/results.json",
        "results.json",
    ],
    "aggregates.json": [
        "artifacts/abm/aggregates.json",
        "aggregates.json",
    ],
    "events.jsonl": [
        "artifacts/abm/events.jsonl",
        "events.jsonl",
    ],
}

def first_existing(repo_root: Path, rels: list[str]) -> Path | None:
    for r in rels:
        p = repo_root / r
        if p.exists() and p.is_file():
            return p
    return None

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, help="Target output directory (e.g., ABM_UI/web/data)")
    args = ap.parse_args()

    repo = Path.cwd()
    out = Path(args.out).expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)

    copied = []
    missing = []

    for name, rels in CANDIDATES.items():
        src = first_existing(repo, rels)
        if not src:
            missing.append(name)
            continue
        dst = out / name
        shutil.copyfile(src, dst)
        copied.append((name, str(src), str(dst)))

    # Write a minimal manifest for consumers (optional)
    manifest = out / "bundle_manifest.txt"
    lines = ["ABM_UI_BUNDLE", f"repo={repo}", f"out={out}"]
    for name, src, dst in copied:
        lines.append(f"{name}\tsrc={src}\tdst={dst}")
    if missing:
        lines.append("missing=" + ",".join(missing))
    manifest.write_text("\n".join(lines) + "\n")

    if missing:
        print("WARN: missing artifacts:", ", ".join(missing), file=sys.stderr)

    print("OK: exported bundle to", out)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
