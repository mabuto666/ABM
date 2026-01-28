# ABM Consumption Guide (v1.0)

## Golden path
```bash
python3 .harness/tools/verify.py --check dod
python3 .harness/tools/ralph.py --loop
```

## Artifacts
- events: artifacts/abm/events.jsonl
- aggregates: artifacts/abm/aggregates.json
- benchmark results: artifacts/abm/benchmarks/results.json

## Determinism
- ABM artifacts are append-only and derived-only.
- Recompute aggregates with:
```bash
python3 .harness/tools/abm_aggregate.py --events artifacts/abm/events.jsonl --output artifacts/abm/aggregates.json
```
