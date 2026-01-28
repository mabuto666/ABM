# Receipts Policy

- Receipts are append-only; never deleted or rewritten.
- Multiple receipts per work order are expected (PROMOTE then COMPLETE).
- Exactly one RUN_DONE receipt per run_id.
- receipts/_dispatch snapshots are append-only.
- PROMOTE receipts are retained indefinitely; they are not pruned or rewritten.
- Verifier allows any number of PROMOTE receipts and only requires COMPLETE for done work orders.
- RUN_DONE remains the sole terminal receipt per run_id.
