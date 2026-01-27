# Invariants

## Measurement Invariants
- All metrics are atomic, numeric, time-bound, and attributable to a Work Order and an Execution Cycle.
- Metrics are never shared across Work Orders.
- Throughput and coordination cost are independent measurable dimensions.

## Entity Mutability
- Work Orders are immutable.
- Metric Events are append-only.
- Execution Cycles are append-only.
- Verification Results are append-only.
- Aggregates are derived only.

## Verification Invariants
- Verification is machine-executable, binary, side-effect free, and repeatable.
- Verification gates progress.

## System Boundaries
- ABM surfaces facts; it does not optimize, schedule, resolve failures, or decide correctness beyond declared verification.
