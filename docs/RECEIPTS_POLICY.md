# Receipts Policy

- Receipts are append-only; never deleted or rewritten.
- Multiple receipts per work order are expected (PROMOTE then COMPLETE).
- Exactly one RUN_DONE receipt per run_id.
- receipts/_dispatch snapshots are append-only.
- Note: the initial ABM_A run used a temporary cleanup workaround that removed PROMOTE receipts; future runs must retain PROMOTE receipts.
