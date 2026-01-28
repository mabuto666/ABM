import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from receipt import canonical_json_bytes, RECEIPT_KINDS, TERMINAL_KINDS
    from util import git_diff_name_only, json_read, matches_any, run_cmd
else:
    from .receipt import canonical_json_bytes, RECEIPT_KINDS, TERMINAL_KINDS
    from .util import git_diff_name_only, json_read, matches_any, run_cmd


DISPATCH_PATH = Path(".harness/contracts/dispatch.json")
HOOKS_PATH = Path(".harness/contracts/hooks.json")
REQUIRED_DENY = [
    "**/.env",
    "**/*.pem",
    "**/*token*",
    "**/package-lock.json",
    "**/yarn.lock",
]


def load_dispatch():
    return json_read(DISPATCH_PATH)


def select_active_wo(dispatch):
    work_orders = dispatch.get("work_orders", [])
    ready = [wo for wo in work_orders if wo.get("ready") and not wo.get("done")]
    ready.sort(key=lambda w: (w.get("priority", 0), w.get("id", "")))
    return ready[0] if ready else None


def check_schema():
    errors = []
    if not DISPATCH_PATH.exists():
        return False, ["dispatch.json missing"]
    dispatch = load_dispatch()
    if not isinstance(dispatch, dict):
        return False, ["dispatch.json must be an object"]
    meta = dispatch.get("meta")
    if not isinstance(meta, dict):
        return False, ["meta must be an object"]
    version = meta.get("version")
    if version != "harness.v1":
        return False, ["meta.version must be harness.v1"]
    if "work_orders" not in dispatch or not isinstance(dispatch["work_orders"], list):
        return False, ["work_orders must be a list"]
    ids = set()
    depends_pairs = []
    ready_active = []
    for idx, wo in enumerate(dispatch["work_orders"]):
        prefix = f"work_orders[{idx}]"
        if not isinstance(wo, dict):
            errors.append(f"{prefix} must be an object")
            continue
        for key in ["id", "title", "ready", "done", "role", "priority", "scope", "steps", "acceptance", "artifacts"]:
            if key not in wo:
                errors.append(f"{prefix} missing {key}")
        wo_id = wo.get("id")
        if not isinstance(wo_id, str) or not wo_id:
            errors.append(f"{prefix} id must be non-empty string")
        elif wo_id in ids:
            errors.append(f"duplicate id {wo_id}")
        else:
            ids.add(wo_id)
        if not isinstance(wo.get("title"), str) or not wo.get("title"):
            errors.append(f"{prefix} title must be non-empty string")
        if not isinstance(wo.get("ready"), bool):
            errors.append(f"{prefix} ready must be bool")
        if not isinstance(wo.get("done"), bool):
            errors.append(f"{prefix} done must be bool")
        if wo.get("done") and wo.get("ready"):
            errors.append(f"{prefix} done implies ready=false")
        if wo.get("ready") and not wo.get("done"):
            ready_active.append(wo.get("id", "<unknown>"))
        if not isinstance(wo.get("role"), str) or not wo.get("role"):
            errors.append(f"{prefix} role must be non-empty string")
        if not isinstance(wo.get("priority"), int):
            errors.append(f"{prefix} priority must be int")
        depends_on = wo.get("depends_on")
        if depends_on is not None:
            if not isinstance(depends_on, list) or not all(
                isinstance(dep, str) and dep for dep in depends_on
            ):
                errors.append(f"{prefix} depends_on must be list of non-empty strings")
            else:
                depends_pairs.append((prefix, depends_on))
        scope = wo.get("scope")
        if not isinstance(scope, dict):
            errors.append(f"{prefix} scope must be object")
        else:
            allow = scope.get("allow_globs")
            deny = scope.get("deny_globs")
            if not isinstance(allow, list) or not allow:
                errors.append(f"{prefix} scope.allow_globs must be non-empty list")
            if not isinstance(deny, list) or not deny:
                errors.append(f"{prefix} scope.deny_globs must be non-empty list")
            for required in REQUIRED_DENY:
                if isinstance(deny, list) and required not in deny:
                    errors.append(f"{prefix} scope.deny_globs missing {required}")
        steps = wo.get("steps")
        if not isinstance(steps, list) or not steps or not all(isinstance(s, str) and s for s in steps):
            errors.append(f"{prefix} steps must be non-empty list of strings")
        acceptance = wo.get("acceptance")
        if not isinstance(acceptance, list) or not acceptance:
            errors.append(f"{prefix} acceptance must be non-empty list")
        else:
            for a_idx, acc in enumerate(acceptance):
                a_prefix = f"{prefix}.acceptance[{a_idx}]"
                if not isinstance(acc, dict):
                    errors.append(f"{a_prefix} must be object")
                    continue
                if not isinstance(acc.get("name"), str) or not acc.get("name"):
                    errors.append(f"{a_prefix} name must be non-empty string")
                if not isinstance(acc.get("cmd"), str) or not acc.get("cmd"):
                    errors.append(f"{a_prefix} cmd must be non-empty string")
        artifacts = wo.get("artifacts")
        if not isinstance(artifacts, dict):
            errors.append(f"{prefix} artifacts must be object")
        else:
            if artifacts.get("receipt_required") is not True:
                errors.append(f"{prefix} artifacts.receipt_required must be true")
    if len(ready_active) > 1:
        errors.append(
            f"multiple_ready_work_orders(n={len(ready_active)}): {', '.join(ready_active)}"
        )
    for prefix, depends_on in depends_pairs:
        for dep in depends_on:
            if dep not in ids:
                errors.append(f"{prefix} depends_on missing id {dep}")
    return not errors, errors


def check_receipts():
    dispatch = load_dispatch()
    errors = []
    receipts_dir = Path("receipts")
    if not receipts_dir.exists():
        return not errors, errors

    work_orders = {wo.get("id"): wo for wo in dispatch.get("work_orders", [])}
    complete_counts = {}
    terminal_counts = {}
    timestamp_re = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
    filename_re = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z-[0-9a-f]{8}\.json$")
    snapshot_dir = receipts_dir / "_dispatch"
    snapshot_name_re = re.compile(r"^[0-9a-f]{64}\.json$")

    def validate_snapshot(path):
        rel_path = path.as_posix()
        name = path.name
        if not snapshot_name_re.match(name):
            errors.append(f"{rel_path} invalid snapshot filename")
            return
        expected_hash = name.split(".", 1)[0]
        try:
            data = path.read_bytes()
        except OSError as exc:
            errors.append(f"{rel_path} unreadable: {exc}")
            return
        if hashlib.sha256(data).hexdigest() != expected_hash:
            errors.append(f"{rel_path} snapshot hash mismatch")
            return
        try:
            payload = json.loads(data.decode("utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"{rel_path} invalid json: {exc}")
            return
        if not isinstance(payload, dict):
            errors.append(f"{rel_path} snapshot must be object")
            return
        try:
            json.dumps(payload, sort_keys=True, separators=(",", ":"))
        except TypeError:
            errors.append(f"{rel_path} snapshot not canonicalizable")

    if snapshot_dir.exists():
        for path in sorted(snapshot_dir.iterdir()):
            if path.is_file():
                validate_snapshot(path)

    for path in sorted(receipts_dir.rglob("*.json")):
        if snapshot_dir in path.parents:
            continue
        rel_path = path.as_posix()
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"{rel_path} invalid json: {exc}")
            continue
        if not isinstance(payload, dict):
            errors.append(f"{rel_path} receipt must be object")
            continue
        allowed_keys = {
            "run_id",
            "kind",
            "timestamp_utc",
            "head",
            "dispatch_hash",
            "work_order_id",
            "summary",
        }
        required_keys = {
            "run_id",
            "kind",
            "timestamp_utc",
            "head",
            "dispatch_hash",
            "work_order_id",
        }
        keys = set(payload.keys())
        extra = keys - allowed_keys
        missing = required_keys - keys
        if extra:
            errors.append(f"{rel_path} unknown keys: {', '.join(sorted(extra))}")
        if missing:
            errors.append(f"{rel_path} missing keys: {', '.join(sorted(missing))}")
        if missing:
            continue
        if not isinstance(payload.get("run_id"), str):
            errors.append(f"{rel_path} run_id must be string")
        kind = payload.get("kind")
        if kind not in RECEIPT_KINDS:
            errors.append(f"{rel_path} kind must be one of {', '.join(sorted(RECEIPT_KINDS))}")
        timestamp_utc = payload.get("timestamp_utc")
        if not isinstance(timestamp_utc, str) or not timestamp_re.match(timestamp_utc):
            errors.append(f"{rel_path} timestamp_utc must be ISO-8601 Z")
        if not isinstance(payload.get("head"), str):
            errors.append(f"{rel_path} head must be string")
        dispatch_hash = payload.get("dispatch_hash")
        if not isinstance(dispatch_hash, str):
            errors.append(f"{rel_path} dispatch_hash must be string")
        else:
            snapshot_path = snapshot_dir / f"{dispatch_hash}.json"
            if not snapshot_path.exists():
                errors.append(f"{rel_path} missing dispatch snapshot {snapshot_path.as_posix()}")
            else:
                snapshot_bytes = snapshot_path.read_bytes()
                if hashlib.sha256(snapshot_bytes).hexdigest() != dispatch_hash:
                    errors.append(f"{rel_path} dispatch snapshot hash mismatch {snapshot_path.as_posix()}")
        if payload.get("work_order_id") is not None and not isinstance(payload.get("work_order_id"), str):
            errors.append(f"{rel_path} work_order_id must be string or null")
        summary = payload.get("summary")
        if "summary" in payload:
            if not isinstance(summary, dict):
                errors.append(f"{rel_path} summary must be object")
            else:
                for key in summary.keys():
                    if not isinstance(key, str):
                        errors.append(f"{rel_path} summary keys must be strings")
                        break
                try:
                    json.dumps(summary, sort_keys=True, separators=(",", ":"))
                except TypeError:
                    errors.append(f"{rel_path} summary must be json-serializable")

        filename = path.name
        if not filename_re.match(filename):
            errors.append(f"{rel_path} filename not deterministic")
        else:
            if isinstance(timestamp_utc, str):
                canonical = canonical_json_bytes(payload)
                short_hash = hashlib.sha256(canonical).hexdigest()[:8]
                expected = f"{timestamp_utc}-{short_hash}.json"
                if filename != expected:
                    errors.append(f"{rel_path} filename hash mismatch")

        wo_id = payload.get("work_order_id")
        if kind in ("PROMOTE", "COMPLETE"):
            if not isinstance(wo_id, str) or not wo_id:
                errors.append(f"{rel_path} work_order_id required for {kind}")
            elif wo_id not in work_orders:
                errors.append(f"{rel_path} unknown work_order_id {wo_id}")
            else:
                wo = work_orders[wo_id]
                # PROMOTE receipts are append-only and do not need to match current ready/done state.
                if kind == "COMPLETE":
                    if not wo.get("done") or wo.get("ready"):
                        errors.append(f"{rel_path} complete requires done=true ready=false")
        else:
            if wo_id is not None:
                errors.append(f"{rel_path} work_order_id must be null for {kind}")

        if kind == "COMPLETE" and isinstance(wo_id, str):
            count = complete_counts.get(wo_id, 0) + 1
            complete_counts[wo_id] = count
            if count > 1:
                errors.append(f"{rel_path} multiple COMPLETE receipts for {wo_id}")

        if kind in TERMINAL_KINDS and isinstance(payload.get("run_id"), str):
            run_id = payload["run_id"]
            count = terminal_counts.get(run_id, 0) + 1
            terminal_counts[run_id] = count
            if count > 1:
                errors.append(f"{rel_path} multiple terminal receipts for run_id {run_id}")

    for wo_id, wo in work_orders.items():
        if wo.get("done") and complete_counts.get(wo_id, 0) < 1:
            errors.append(f"receipts missing COMPLETE for done work order {wo_id}")

    return not errors, errors


def check_scope():
    dispatch = load_dispatch()
    wo = select_active_wo(dispatch)
    if not wo:
        return True, []
    scope = wo["scope"]
    allow = scope["allow_globs"]
    deny = scope["deny_globs"]
    head = run_cmd(["git", "rev-parse", "--verify", "HEAD"])
    head_exists = head["code"] == 0
    tracked = []
    if head_exists:
        diff = git_diff_name_only()
        if diff["code"] != 0:
            return False, ["git diff failed"]
        tracked = [line.strip() for line in diff["stdout"].splitlines() if line.strip()]
    untracked = run_cmd(["git", "ls-files", "--others", "--exclude-standard"])
    if untracked["code"] != 0:
        return False, ["git ls-files failed"]
    untracked_files = [line.strip() for line in untracked["stdout"].splitlines() if line.strip()]
    changed = sorted(set(tracked + untracked_files))
    errors = []
    for path in changed:
        if matches_any(path, deny):
            errors.append(f"scope denied: {path}")
        if not matches_any(path, allow):
            errors.append(f"scope not allowed: {path}")
    return not errors, errors


def check_project():
    hooks = json_read(HOOKS_PATH)
    verify_cmd = hooks.get("project", {}).get("verify_cmd", "")
    proof_cmd = hooks.get("project", {}).get("proof_cmd", "")
    if not verify_cmd and not proof_cmd:
        return True, []
    errors = []
    for name, cmd in [("proof_cmd", proof_cmd), ("verify_cmd", verify_cmd)]:
        if not cmd:
            continue
        result = run_cmd(cmd)
        if result["code"] != 0:
            errors.append(f"{name} failed: {cmd}")
            errors.append(result["stderr"] or result["stdout"])
    return not errors, errors


def check_no_ready_undone():
    dispatch = load_dispatch()
    pending = [wo["id"] for wo in dispatch.get("work_orders", []) if wo.get("ready") and not wo.get("done")]
    if pending:
        return False, [f"ready but not done: {', '.join(pending)}"]
    return True, []


def run_check(name):
    checks = {
        "schema": check_schema,
        "receipts": check_receipts,
        "scope": check_scope,
        "project": check_project,
        "no_ready_undone": check_no_ready_undone,
    }
    ok, errors = checks[name]()
    if ok:
        print(f"{name}: OK")
    else:
        print(f"{name}: FAIL")
        for err in errors:
            print(f"- {err}")
    return ok


def run_checks(order):
    ok = True
    for name in order:
        ok = run_check(name) and ok
    return ok


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check",
        choices=["schema", "work", "dod"],
        default="dod",
    )
    args = parser.parse_args()

    if args.check == "schema":
        order = ["schema"]
    elif args.check == "work":
        order = ["schema", "receipts", "scope", "project"]
    else:
        order = ["schema", "receipts", "scope", "project", "no_ready_undone"]

    return 0 if run_checks(order) else 1


if __name__ == "__main__":
    raise SystemExit(main())
