import argparse
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from util import json_read, json_write, run_cmd
else:
    from .util import json_read, json_write, run_cmd


DISPATCH_PATH = Path(".harness/contracts/dispatch.json")


def set_ready(wo_id):
    dispatch = json_read(DISPATCH_PATH)
    found = False
    for wo in dispatch.get("work_orders", []):
        if not wo.get("done"):
            wo["ready"] = False
        if wo.get("id") == wo_id:
            found = True
            if wo.get("done"):
                raise SystemExit(f"work order already done: {wo_id}")
            wo["ready"] = True
    if not found:
        raise SystemExit(f"unknown work order: {wo_id}")
    json_write(DISPATCH_PATH, dispatch)
    return dispatch


def commit_ready(wo_id):
    run_cmd(["git", "add", str(DISPATCH_PATH)], check=True)
    run_cmd(["git", "commit", "-m", f"dispatch: ready {wo_id}"], check=True)


def main():
    parser = argparse.ArgumentParser(description="Debug helper for dispatch readiness.")
    parser.add_argument("--ready", required=True, help="Work order ID to mark ready.")
    args = parser.parse_args()

    before = run_cmd(["git", "status", "--porcelain", str(DISPATCH_PATH)])
    _ = set_ready(args.ready)
    after = run_cmd(["git", "status", "--porcelain", str(DISPATCH_PATH)])
    if before["stdout"] == after["stdout"] and not after["stdout"]:
        print(f"dispatch already set: {args.ready}")
        return 0
    commit_ready(args.ready)
    print(f"ready set: {args.ready}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
