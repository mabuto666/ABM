import argparse
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import abm as abm_mod
    import verify as verify_mod
    from receipt import dispatch_hash, make_run_id, write_receipt
    from util import git_changed_files, git_head, json_read, json_write, now_iso, run_cmd
else:
    from . import abm as abm_mod
    from . import verify as verify_mod
    from .receipt import dispatch_hash, make_run_id, write_receipt
    from .util import git_changed_files, git_head, json_read, json_write, now_iso, run_cmd


DISPATCH_PATH = Path(".harness/contracts/dispatch.json")
STATUS_PATH = Path("docs/STATUS.md")


def ensure_git_repo():
    if Path(".git").exists():
        return True
    result = run_cmd(["git", "init"])
    return result["code"] == 0


def append_status(line):
    STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(STATUS_PATH, "a", encoding="utf-8") as fh:
        fh.write(f"{now_iso()} {line}\n")


def select_ready_wo(dispatch):
    work_orders = dispatch.get("work_orders", [])
    ready = [wo for wo in work_orders if wo.get("ready") and not wo.get("done")]
    ready.sort(key=lambda w: (w.get("priority", 0), w.get("id", "")))
    return ready[0] if ready else None


def select_ready_ids(dispatch):
    work_orders = dispatch.get("work_orders", [])
    ready = [wo for wo in work_orders if wo.get("ready") and not wo.get("done")]
    ready.sort(key=lambda w: (w.get("priority", 0), w.get("id", "")))
    return [wo.get("id", "<unknown>") for wo in ready]


def select_next_eligible(dispatch):
    work_orders = dispatch.get("work_orders", [])
    done_ids = {wo.get("id") for wo in work_orders if wo.get("done")}
    eligible = []
    for wo in work_orders:
        if wo.get("done"):
            continue
        depends_on = wo.get("depends_on") or []
        if all(dep in done_ids for dep in depends_on):
            eligible.append(wo)
    eligible.sort(key=lambda w: (w.get("priority", 0), w.get("id", "")))
    return eligible[0] if eligible else None


def run_acceptance(wo):
    results = []
    ok = True
    for acc in wo["acceptance"]:
        result = run_cmd(acc["cmd"])
        result["name"] = acc["name"]
        results.append(result)
        if result["code"] != 0:
            ok = False
    return ok, results


def run_verify_work():
    checks = [
        ("schema", verify_mod.check_schema),
        ("receipts", verify_mod.check_receipts),
        ("scope", verify_mod.check_scope),
        ("abm", verify_mod.check_abm),
        ("project", verify_mod.check_project),
    ]
    ok = True
    errors = {}
    for name, func in checks:
        passed, errs = func()
        errors[name] = errs
        ok = ok and passed
    return ok, errors


def run_verify_dod():
    checks = [
        ("schema", verify_mod.check_schema),
        ("receipts", verify_mod.check_receipts),
        ("scope", verify_mod.check_scope),
        ("abm", verify_mod.check_abm),
        ("project", verify_mod.check_project),
        ("no_ready_undone", verify_mod.check_no_ready_undone),
    ]
    ok = True
    errors = {}
    for name, func in checks:
        passed, errs = func()
        errors[name] = errs
        ok = ok and passed
    return ok, errors


def mark_done(dispatch, wo_id):
    for wo in dispatch.get("work_orders", []):
        if wo.get("id") == wo_id:
            wo["done"] = True
            wo["ready"] = False
    json_write(DISPATCH_PATH, dispatch)


def commit_work(wo_id):
    run_cmd(["git", "add", "-A"], check=True)
    run_cmd(["git", "commit", "-m", f"ralph: complete {wo_id}"], check=True)


def commit_promotion(wo_id):
    run_cmd(["git", "add", str(DISPATCH_PATH)], check=True)
    run_cmd(["git", "commit", "-m", f"ralph: promote {wo_id}"], check=True)


def promote_next(dispatch, run_id, cycle_id, agent_id, head, dispatch_hash_value):
    wo = select_next_eligible(dispatch)
    if not wo:
        return None
    for item in dispatch.get("work_orders", []):
        if item.get("id") == wo.get("id"):
            item["ready"] = True
            break
    json_write(DISPATCH_PATH, dispatch)
    commit_promotion(wo["id"])
    abm_mod.append_event(
        abm_mod.build_event(
            "state_transition",
            run_id,
            dispatch_hash_value,
            head,
            wo["id"],
            cycle_id,
            agent_id,
            detail={"to_state": "ready"},
        )
    )
    write_receipt(
        "PROMOTE",
        run_id=run_id,
        head=git_head(),
        dispatch_hash_value=dispatch_hash(),
        work_order_id=wo["id"],
    )
    return wo["id"]


def run_verify_cmd(mode):
    result = run_cmd(["python3", ".harness/tools/verify.py", "--check", mode])
    return result["code"] == 0, result


def one_cycle(run_id):
    if not ensure_git_repo():
        print("git repo missing", file=sys.stderr)
        return 1

    dispatch = json_read(DISPATCH_PATH)
    ready_ids = select_ready_ids(dispatch)
    if len(ready_ids) > 1:
        print(
            f"multiple ready work orders (wip=1): {', '.join(ready_ids)}",
            file=sys.stderr,
        )
        write_receipt(
            "RUN_FAIL",
            run_id=run_id,
            head=git_head(),
            dispatch_hash_value=dispatch_hash(),
            work_order_id=None,
        )
        return 1

    wo = select_ready_wo(dispatch)
    head = git_head()
    dispatch_hash_value = dispatch_hash()
    agent_id = "ralph"
    cycle_id = None
    if not wo:
        promoted = promote_next(
            dispatch,
            run_id,
            cycle_id,
            agent_id,
            head,
            dispatch_hash_value,
        )
        if promoted:
            append_status(f"PROMOTE {promoted}")
            abm_mod.write_aggregates()
            return 0
        dod_ok, _ = run_verify_cmd("dod")
        if dod_ok:
            append_status("DONE DoD=PASS")
            write_receipt(
                "RUN_DONE",
                run_id=run_id,
                head=git_head(),
                dispatch_hash_value=dispatch_hash(),
                work_order_id=None,
            )
            print("DONE")
            abm_mod.write_aggregates()
            return 2
        append_status("FAIL DoD=FAIL")
        write_receipt(
            "RUN_FAIL",
            run_id=run_id,
            head=git_head(),
            dispatch_hash_value=dispatch_hash(),
            work_order_id=None,
        )
        abm_mod.write_aggregates()
        return 1

    cycle_id = abm_mod.next_cycle_id(run_id)
    abm_mod.append_event(
        abm_mod.build_event(
            "cycle_start",
            run_id,
            dispatch_hash_value,
            head,
            wo["id"],
            cycle_id,
            agent_id,
        )
    )
    attempt_id = "attempt-1"
    abm_mod.append_event(
        abm_mod.build_event(
            "attempt_start",
            run_id,
            dispatch_hash_value,
            head,
            wo["id"],
            cycle_id,
            agent_id,
            detail={"attempt_id": attempt_id},
        )
    )
    abm_mod.append_event(
        abm_mod.build_event(
            "verify_start",
            run_id,
            dispatch_hash_value,
            head,
            wo["id"],
            cycle_id,
            agent_id,
        )
    )
    abm_mod.write_aggregates()

    acceptance_ok, acceptance_results = run_acceptance(wo)
    scope_ok, scope_errors = verify_mod.check_scope()
    verify_ok, verify_errors = run_verify_work()
    run_verify_cmd("work")
    dod_ok_after, dod_errors_after = run_verify_dod()
    abm_mod.append_event(
        abm_mod.build_event(
            "verify_result",
            run_id,
            dispatch_hash_value,
            head,
            wo["id"],
            cycle_id,
            agent_id,
            detail={
                "status": "pass" if (acceptance_ok and scope_ok and verify_ok) else "fail"
            },
        )
    )
    abm_mod.append_event(
        abm_mod.build_event(
            "attempt_end",
            run_id,
            dispatch_hash_value,
            head,
            wo["id"],
            cycle_id,
            agent_id,
            detail={
                "attempt_id": attempt_id,
                "status": "pass" if (acceptance_ok and scope_ok and verify_ok) else "fail",
            },
        )
    )

    if acceptance_ok and scope_ok and verify_ok:
        mark_done(dispatch, wo["id"])
        abm_mod.append_event(
            abm_mod.build_event(
                "state_transition",
                run_id,
                dispatch_hash_value,
                head,
                wo["id"],
                cycle_id,
                agent_id,
                detail={"to_state": "done"},
            )
        )
        commit_work(wo["id"])
        write_receipt(
            "COMPLETE",
            run_id=run_id,
            head=git_head(),
            dispatch_hash_value=dispatch_hash(),
            work_order_id=wo["id"],
        )
        append_status(f"PASS {wo['id']}")
        dispatch = json_read(DISPATCH_PATH)
        promoted = promote_next(
            dispatch,
            run_id,
            cycle_id,
            agent_id,
            head,
            dispatch_hash_value,
        )
        if promoted:
            append_status(f"PROMOTE {promoted}")
            abm_mod.append_event(
                abm_mod.build_event(
                    "cycle_end",
                    run_id,
                    dispatch_hash_value,
                    head,
                    wo["id"],
                    cycle_id,
                    agent_id,
                    detail={"status": "pass"},
                )
            )
            abm_mod.write_aggregates()
            return 0
        dod_ok, _ = run_verify_cmd("dod")
        if dod_ok:
            append_status("DONE DoD=PASS")
            write_receipt(
                "RUN_DONE",
                run_id=run_id,
                head=git_head(),
                dispatch_hash_value=dispatch_hash(),
                work_order_id=None,
            )
            print("DONE")
            abm_mod.append_event(
                abm_mod.build_event(
                    "cycle_end",
                    run_id,
                    dispatch_hash_value,
                    head,
                    wo["id"],
                    cycle_id,
                    agent_id,
                    detail={"status": "pass"},
                )
            )
            abm_mod.write_aggregates()
            return 2
        append_status("FAIL DoD=FAIL")
        write_receipt(
            "RUN_FAIL",
            run_id=run_id,
            head=git_head(),
            dispatch_hash_value=dispatch_hash(),
            work_order_id=None,
        )
        abm_mod.append_event(
            abm_mod.build_event(
                "cycle_end",
                run_id,
                dispatch_hash_value,
                head,
                wo["id"],
                cycle_id,
                agent_id,
                detail={"status": "fail"},
            )
        )
        abm_mod.write_aggregates()
        return 1

    append_status(f"FAIL {wo['id']}")
    write_receipt(
        "RUN_FAIL",
        run_id=run_id,
        head=git_head(),
        dispatch_hash_value=dispatch_hash(),
        work_order_id=None,
    )
    abm_mod.append_event(
        abm_mod.build_event(
            "cycle_end",
            run_id,
            dispatch_hash_value,
            head,
            wo["id"],
            cycle_id,
            agent_id,
            detail={"status": "fail"},
        )
    )
    abm_mod.write_aggregates()
    return 1


def main():
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--once", action="store_true")
    group.add_argument("--loop", action="store_true")
    args = parser.parse_args()
    run_id = make_run_id()

    if args.once:
        code = one_cycle(run_id)
        return 0 if code == 2 else code

    while True:
        code = one_cycle(run_id)
        if code != 0:
            return 0 if code == 2 else code


if __name__ == "__main__":
    raise SystemExit(main())
