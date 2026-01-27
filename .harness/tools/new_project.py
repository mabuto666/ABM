import argparse
import shutil
import subprocess
from pathlib import Path


def write_json(path: Path, payload: dict) -> None:
    import json

    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def write_prd_stub(target_root: Path, name: str) -> None:
    prd_path = target_root / "docs" / "PRD.md"
    prd_path.parent.mkdir(parents=True, exist_ok=True)
    content = """# Product Requirements Document

## Project
- Name: {name}

## Goals
- 

## Non-Goals
- 

## Scope
- 

## Success Criteria
- 
""".format(name=name)
    prd_path.write_text(content, encoding="utf-8")


def write_dispatch(target_root: Path) -> None:
    dispatch_path = target_root / ".harness" / "contracts" / "dispatch.json"
    dispatch = {
        "meta": {"version": "harness.v1"},
        "work_orders": [
            {
                "id": "WO-0001",
                "title": "Mayor: write PRD and generate work orders",
                "ready": True,
                "done": False,
                "role": "MAYOR",
                "priority": 1,
                "depends_on": [],
                "scope": {
                    "allow_globs": [
                        ".harness/**",
                        "docs/**",
                        "README.md",
                        "Taskfile.yml",
                        "receipts/**",
                        "docs/STATUS.md",
                    ],
                    "deny_globs": [
                        "**/.env",
                        "**/*.pem",
                        "**/*token*",
                        "**/package-lock.json",
                        "**/yarn.lock",
                        "**/__pycache__/**",
                        "**/*.pyc",
                    ],
                },
                "steps": [
                    "Create or expand docs/PRD.md with clear goals, scope, and success criteria.",
                    "Replace .harness/contracts/dispatch.json with project work orders.",
                    "Mark WO-0001 done once the new dispatch is in place.",
                ],
                "acceptance": [
                    {
                        "name": "doctor",
                        "cmd": "python3 .harness/tools/doctor.py",
                    },
                    {
                        "name": "verify-schema",
                        "cmd": "python3 .harness/tools/verify.py --check schema",
                    }
                ],
                "artifacts": {"receipt_required": True},
            }
        ],
    }
    write_json(dispatch_path, dispatch)


def copy_repo(src: Path, dst: Path) -> None:
    ignore = shutil.ignore_patterns(".git", "__pycache__")
    shutil.copytree(src, dst, ignore=ignore)


def init_git(dst: Path) -> None:
    subprocess.run(["git", "init"], cwd=dst, check=True)


def init_commit(dst: Path, name: str) -> None:
    subprocess.run(["git", "add", "-A"], cwd=dst, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=ORC",
            "-c",
            "user.email=orc@local",
            "commit",
            "-m",
            f"init: {name}",
        ],
        cwd=dst,
        check=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    src = Path.cwd()
    dst = Path(args.out).expanduser().resolve()
    if dst.exists():
        raise SystemExit(f"destination exists: {dst}")

    copy_repo(src, dst)
    init_git(dst)
    write_prd_stub(dst, args.name)
    write_dispatch(dst)
    init_commit(dst, args.name)

    print("Next commands:")
    print(f"cd {dst}")
    print("python3 .harness/tools/doctor.py")
    print("python3 .harness/tools/verify.py")
    print("python3 .harness/tools/promptgen.py")
    print("python3 .harness/tools/ralph.py --loop")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
