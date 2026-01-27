import json
import os
import subprocess
from datetime import datetime, timezone
from fnmatch import fnmatch
from pathlib import Path


def now_iso():
    override = os.environ.get("HARNESS_NOW_ISO")
    if override:
        return override
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def json_read(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def json_write(path, data):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, sort_keys=True)
        fh.write("\n")


def run_cmd(cmd, check=False):
    result = subprocess.run(
        cmd,
        shell=isinstance(cmd, str),
        text=True,
        capture_output=True,
    )
    if check and result.returncode != 0:
        raise RuntimeError(
            f"Command failed ({result.returncode}): {cmd}\n{result.stderr}"
        )
    return {
        "cmd": cmd,
        "code": result.returncode,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
    }


def git_head():
    result = run_cmd(["git", "rev-parse", "HEAD"])
    return result["stdout"] if result["code"] == 0 else ""


def git_status_short():
    return run_cmd(["git", "status", "--short"])  # includes untracked


def git_diff_name_only():
    return run_cmd(["git", "diff", "--name-only", "HEAD"])


def git_changed_files():
    diff = git_diff_name_only()
    files = set(line.strip() for line in diff["stdout"].splitlines() if line.strip())
    status = git_status_short()
    for line in status["stdout"].splitlines():
        parts = line.split()
        if len(parts) == 2:
            files.add(parts[1])
    return sorted(files)


def matches_any(path, patterns):
    return any(fnmatch(path, pat) for pat in patterns)
