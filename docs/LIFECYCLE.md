# Lifecycle

## Execution Cycle Emission
For each Execution Cycle, ABM emits metrics across the following stages:
1. Cycle start
2. Execution attempt(s)
3. Verification
4. State transition
5. Cycle end

## Aggregation
- Aggregation is post-hoc only.
- Aggregates never influence execution.
- Aggregates freeze after terminal halt.

## Run Finalization
A Run is finalized when:
- No ready Work Orders remain, or
- A deterministic halt condition is met.
