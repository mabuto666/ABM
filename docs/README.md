# ABM Documentation

## Reviews & ADRs
- [ABM Engineering Review — Executive Findings](reviews/ABM_ENGINEERING_REVIEW_BASELINE.md)
- [Baseline Review Process (ABM)](adr/REVIEW_PROCESS.md)
- [ADR Index](adr/README.md)
- [ADR-0001: ABM Engineering Baseline and Determinism Corrections](adr/ADR-0001-abm-engineering-baseline-and-determinism-corrections.md)

## Harness Upgrades
- [Harness Upstream Provenance](HARNESS_UPSTREAM.md)
- Use `task sync:harness` to sync the allowlist and re-verify DoD.

## Testing
- Harness: `task smoke`, `python3 .harness/tools/verify.py --check dod`
- ABM: `task test:abm`
- ABM agent tests (budget/behavior): `task test:agent`
- ABM agent suites (N runs + gate): `task agent:suite` or `task agent:suite10`
- Real-time view: `task watch:abm` or `task serve:abm`
- ABM agent testing baseline files are part of this change because they were missing in main.
