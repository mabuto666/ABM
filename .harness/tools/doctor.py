import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from util import git_head, git_status_short
else:
    from .util import git_head, git_status_short


REQUIRED_PATHS = [
    ".harness",
    ".harness/contracts/dispatch.json",
    ".harness/contracts/schema_dispatch.json",
    ".harness/contracts/dod.json",
    ".harness/contracts/hooks.json",
    ".harness/tools",
    "receipts",
    "docs/STATUS.md",
]


def main():
    if sys.version_info < (3, 9):
        print("Python 3.9+ required", file=sys.stderr)
        return 1
    missing = [p for p in REQUIRED_PATHS if not Path(p).exists()]
    if missing:
        print("Missing required paths:", file=sys.stderr)
        for p in missing:
            print(f"- {p}", file=sys.stderr)
        return 1
    head = git_head()
    status = git_status_short()
    print(f"git_head={head}")
    if status["stdout"]:
        print("git_status_short=")
        print(status["stdout"])
    else:
        print("git_status_short=clean")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
