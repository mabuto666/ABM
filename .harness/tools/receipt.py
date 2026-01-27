import hashlib
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
else:
    pass


RECEIPTS_DIR = Path("receipts")
RUN_DIR = "RUN"
RECEIPT_KINDS = {"PROMOTE", "COMPLETE", "RUN_DONE", "RUN_FAIL"}
TERMINAL_KINDS = {"RUN_DONE", "RUN_FAIL"}


def now_utc_z():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def make_run_id():
    return f"{now_utc_z()}-{uuid.uuid4().hex[:8]}"


def canonical_json_bytes(payload):
    return (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def sha256_hex(data):
    return hashlib.sha256(data).hexdigest()


def canonical_dispatch_bytes(dispatch_path=Path(".harness/contracts/dispatch.json")):
    data = json.loads(dispatch_path.read_text(encoding="utf-8"))
    return canonical_json_bytes(data)


def dispatch_hash(dispatch_path=Path(".harness/contracts/dispatch.json")):
    return sha256_hex(canonical_dispatch_bytes(dispatch_path))


def receipt_filename(payload):
    short_hash = sha256_hex(canonical_json_bytes(payload))[:8]
    return f"{payload['timestamp_utc']}-{short_hash}.json"


def receipt_dir(kind, work_order_id):
    if kind in ("PROMOTE", "COMPLETE"):
        if not work_order_id:
            raise ValueError("work_order_id required for PROMOTE/COMPLETE")
        return RECEIPTS_DIR / work_order_id
    return RECEIPTS_DIR / RUN_DIR


def build_receipt(kind, run_id, head, dispatch_hash_value, work_order_id=None, summary=None):
    if kind not in RECEIPT_KINDS:
        raise ValueError(f"unknown receipt kind: {kind}")
    if kind in ("PROMOTE", "COMPLETE"):
        if not isinstance(work_order_id, str) or not work_order_id:
            raise ValueError("work_order_id required for PROMOTE/COMPLETE")
    else:
        if work_order_id is not None:
            raise ValueError(f"work_order_id must be null for {kind}")
    if summary is not None:
        if not isinstance(summary, dict):
            raise ValueError("summary must be an object when present")
        for key in summary.keys():
            if not isinstance(key, str):
                raise ValueError("summary keys must be strings")
        json.dumps(summary, sort_keys=True, separators=(",", ":"))
    payload = {
        "run_id": run_id,
        "kind": kind,
        "timestamp_utc": now_utc_z(),
        "head": head,
        "dispatch_hash": dispatch_hash_value,
        "work_order_id": work_order_id,
    }
    if summary is not None:
        payload["summary"] = summary
    return payload


def write_receipt(kind, run_id, head, dispatch_hash_value, work_order_id=None, summary=None):
    dispatch_bytes = canonical_dispatch_bytes()
    dispatch_hash_value = sha256_hex(dispatch_bytes)
    dispatch_dir = RECEIPTS_DIR / "_dispatch"
    dispatch_dir.mkdir(parents=True, exist_ok=True)
    snapshot_path = dispatch_dir / f"{dispatch_hash_value}.json"
    if not snapshot_path.exists():
        with open(snapshot_path, "x", encoding="utf-8") as fh:
            fh.write(dispatch_bytes.decode("utf-8"))
    else:
        existing = snapshot_path.read_bytes()
        if sha256_hex(existing) != dispatch_hash_value:
            raise RuntimeError(f"dispatch snapshot hash mismatch: {snapshot_path}")
    payload = build_receipt(kind, run_id, head, dispatch_hash_value, work_order_id, summary)
    target_dir = receipt_dir(kind, work_order_id)
    target_dir.mkdir(parents=True, exist_ok=True)
    filename = receipt_filename(payload)
    path = target_dir / filename
    if path.exists():
        raise FileExistsError(f"receipt exists: {path}")
    with open(path, "x", encoding="utf-8") as fh:
        fh.write(canonical_json_bytes(payload).decode("utf-8"))
    return str(path)


if __name__ == "__main__":
    example = build_receipt(
        "PROMOTE",
        run_id=make_run_id(),
        head="HEAD",
        dispatch_hash_value="0" * 64,
        work_order_id="WO-EXAMPLE",
        summary={"note": "example"},
    )
    print(receipt_filename(example))
