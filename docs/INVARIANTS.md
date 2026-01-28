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

## Guardrail Thresholds
- Max cycles without completion per Work Order: 3.
- Max verification fail streak without state change: 3.
- Max cycles per Work Order: 10.

## Scaling Limit Thresholds
- Throughput collapse: zero done transitions after at least one cycle.
- Coordination dominance threshold: throughput_to_coordination <= 0.25.
- Verification drag threshold: verify_fail / (verify_pass + verify_fail) >= 0.5.
- Retry amplification threshold: attempt_count / cycle_count >= 2.0.

## System Boundaries
- ABM surfaces facts; it does not optimize, schedule, resolve failures, or decide correctness beyond declared verification.
