import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from util import json_read
else:
    from .util import json_read


def select_active_wo(dispatch):
    work_orders = dispatch.get("work_orders", [])
    ready = [wo for wo in work_orders if wo.get("ready") and not wo.get("done")]
    ready.sort(key=lambda w: (w.get("priority", 0), w.get("id", "")))
    return ready[0] if ready else None


def main():
    dispatch = json_read(".harness/contracts/dispatch.json")
    wo = select_active_wo(dispatch)
    if not wo:
        print("NO_READY_WORK_ORDERS")
        return 0

    print(f"WO {wo['id']}: {wo['title']}")
    print("ALLOW_GLOBS:")
    for item in wo["scope"]["allow_globs"]:
        print(f"- {item}")
    print("DENY_GLOBS:")
    for item in wo["scope"]["deny_globs"]:
        print(f"- {item}")
    print("STEPS:")
    for step in wo["steps"]:
        print(f"- {step}")
    print("ACCEPTANCE:")
    for acc in wo["acceptance"]:
        print(f"- {acc['name']}: {acc['cmd']}")
    print("OUTPUT CONTRACT:")
    print("- Apply only the allowed scope; do not touch denied paths.")
    print("- Make atomic changes to satisfy all steps.")
    print("- Ensure acceptance commands pass.")
    print("- Report files changed and a short completion note.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
