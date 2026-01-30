import os
import sys
import tempfile
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from receipt import write_receipt
    try:
        from util import resolve_cmd_spec as resolve_cmd_spec
    except ImportError:
        resolve_cmd_spec = None
    from util import run_cmd as util_run_cmd
else:
    from .receipt import write_receipt
    try:
        from .util import resolve_cmd_spec as resolve_cmd_spec
    except ImportError:
        resolve_cmd_spec = None
    from .util import run_cmd as util_run_cmd


def run_cmd(cmd, allow_shell=False):
    if isinstance(cmd, str) and not allow_shell:
        raise ValueError("String commands require shell=true opt-in; prefer list-form cmd: [...]")
    return util_run_cmd(cmd)


def _resolve_cmd_spec(spec, context="command"):
    if resolve_cmd_spec:
        return resolve_cmd_spec(spec, context=context)
    if spec in (None, "", []):
        return None, None
    cmd = spec
    shell_opt_in = False
    if isinstance(spec, dict):
        cmd = spec.get("cmd")
        shell_opt_in = bool(spec.get("shell", False))
    if cmd in (None, "", []):
        return None, None
    if isinstance(cmd, list):
        if not cmd or not all(isinstance(item, str) and item for item in cmd):
            raise ValueError(f"{context} cmd must be a non-empty list of strings")
        if shell_opt_in:
            raise ValueError(f"{context} shell=true requires string cmd; prefer list-form cmd: [...]")
        return cmd, False
    if isinstance(cmd, str):
        if not shell_opt_in:
            raise ValueError("String commands require shell=true opt-in; prefer list-form cmd: [...]")
        return cmd, True
    raise ValueError(f"{context} cmd must be a list or string")


def run():
    errors = []

    print("smoke: verify dod")
    result = run_cmd([sys.executable, ".harness/tools/verify.py", "--check", "dod"])
    if result["code"] != 0:
        errors.append("verify dod failed")
        if result["stderr"]:
            errors.append(result["stderr"])

    print("smoke: receipt write")
    dispatch_src = Path(".harness/contracts/dispatch.json")
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        contracts_dir = tmp_path / ".harness" / "contracts"
        contracts_dir.mkdir(parents=True, exist_ok=True)
        contracts_dir.joinpath("dispatch.json").write_text(
            dispatch_src.read_text(encoding="utf-8"), encoding="utf-8"
        )
        cwd = Path.cwd()
        os.chdir(tmp_path)
        try:
            write_receipt(
                "RUN_FAIL",
                run_id="smoke-run",
                head="HEAD",
                dispatch_hash_value="0" * 64,
                work_order_id=None,
            )
        except Exception as exc:
            errors.append(f"receipt write failed: {exc}")
        finally:
            os.chdir(cwd)

    print("smoke: shell policy")
    try:
        cmd, allow_shell = _resolve_cmd_spec(["echo", "smoke-ok"], context="smoke list")
        result = run_cmd(cmd, allow_shell=allow_shell)
        if result["code"] != 0:
            errors.append("list command failed")
    except Exception as exc:
        errors.append(f"list command error: {exc}")

    try:
        _resolve_cmd_spec("echo smoke", context="smoke string")
        errors.append("string command without shell=true should fail")
    except ValueError as exc:
        if "String commands require shell=true opt-in" not in str(exc):
            errors.append(f"unexpected string command error: {exc}")

    try:
        cmd, allow_shell = _resolve_cmd_spec(
            {"cmd": "echo smoke-ok", "shell": True}, context="smoke shell"
        )
        result = run_cmd(cmd, allow_shell=allow_shell)
        if result["code"] != 0:
            errors.append("shell command failed")
    except Exception as exc:
        errors.append(f"shell command error: {exc}")

    if errors:
        print("smoke: FAIL")
        for err in errors:
            print(f"- {err}")
        return 1
    print("smoke: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
