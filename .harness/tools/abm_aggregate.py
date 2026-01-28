import argparse
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import abm as abm_mod
else:
    from . import abm as abm_mod


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--events",
        default=str(abm_mod.EVENTS_PATH),
        help="Path to events.jsonl (default: artifacts/abm/events.jsonl)",
    )
    parser.add_argument(
        "--output",
        default="",
        help="Path to aggregates.json (default: alongside events.jsonl)",
    )
    args = parser.parse_args()

    events_path = Path(args.events)
    if not args.output:
        output_path = events_path.parent / "aggregates.json"
    else:
        output_path = Path(args.output)

    abm_mod.write_aggregates_for(events_path=events_path, aggregates_path=output_path)
    print(str(output_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
