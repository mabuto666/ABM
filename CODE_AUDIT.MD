**A) EXECUTIVE SUMMARY (≤10 bullets)**
- Strong: Harness-centric workflow with DoD gating and receipts ledger makes automation flows explicit and auditable (`.harness/tools/verify.py`, `.harness/tools/receipt.py`).
- Strong: Clear separation of contracts vs artifacts vs docs makes intent legible (`contracts/`, `artifacts/`, `docs/`).
- Strong: ABM outputs are portable and UI-friendly via explicit export tool (`tools/export_ui_bundle.py`).
- Risk: Verification strictness changes by environment because `jsonschema` is optional, leading to inconsistent DoD outcomes (`.harness/tools/verify.py`).
- Risk: Benchmark runner chooses “latest” run nondeterministically due to unsorted glob iteration (`.harness/tools/abm_bench.py`).
- Risk: Orchestration mixes policy, IO, git commits, and event emission in a single module, raising coupling and refactor risk (`.harness/tools/ralph.py`).
- Maintainability score: 6.5/10 — clean contracts and docs, but large god modules and mixed concerns add friction.
- Automation-readiness score: 7/10 — DoD gating and receipts are solid, but determinism can drift across environments and runs.

**B) STRUCTURE MAP**
- Annotated tree (top-level)
  - `./.harness/` — ORC-base harness: dispatch contracts, DoD, and tools (ralph/verify/doctor).
  - `./contracts/` — ABM data contracts (event schema, metrics catalog).
  - `./artifacts/` — Generated telemetry outputs (events, aggregates, benchmark results).
  - `./benchmarks/` — Benchmark specs for parameter sweeps.
  - `./docs/` — SDD and invariants; lifecycle and versioning.
  - `./receipts/` — Append-only execution receipts and dispatch snapshots.
  - `./tools/` — ABM utilities (UI bundle exporter).
  - `./.github/` — CI workflows (ABM → ABM_UI smoke).
  - `README.md`, `ARCHITECTURE.MD`, `Taskfile.yml` — Entry guidance and task entrypoints.

- ASCII component diagram
```
[dispatch.json] --> [ralph.py] --> [events.jsonl] --> [abm.py aggregates]
       |               |                |                  |
       |               v                v                  v
       |          [receipts]      [verify.py]       [benchmarks/abm_bench.py]
       |               |                |                  |
       v               v                v                  v
   [docs/STATUS]  [DoD checks]    [abm_event schema]   [results.json + limits]
                                      |
                                      v
                             [export_ui_bundle.py] --> [ABM_UI/web/data]
```

- Key entrypoints list
  - `python3 .harness/tools/ralph.py --loop` (primary execution loop)
  - `python3 .harness/tools/verify.py --check {schema|work|dod}` (DoD gating)
  - `python3 .harness/tools/doctor.py` (env/structure sanity)
  - `python3 .harness/tools/abm_bench.py [--execute]` (benchmark runner)
  - `python3 .harness/tools/abm_aggregate.py` (aggregate rebuild)
  - `python3 .harness/tools/dispatch.py --ready <WO>` (debug helper)
  - `python3 tools/export_ui_bundle.py --out <dir>` (UI bundle export)
  - `Taskfile.yml` task aliases: `doctor`, `verify`, `ralph`, `export:ui`

**C) TOP FINDINGS (ranked)**

1) Severity: High
- Evidence: `.harness/tools/verify.py` `_validate_abm_events_schema` dynamically imports `jsonschema` and falls back to minimal validation when absent.
- Why it matters (impact on complexity/coupling/maintainability): DoD verification strictness changes across machines/CI, undermining deterministic correctness claims.
- Smallest viable fix: Make validation behavior deterministic by always using the same validator (either vendor minimal validator as mandatory or require `jsonschema` with a pinned version).
- Effort: S
- Change risk: Low
- Suggested acceptance criteria: Running `verify.py --check abm` yields identical pass/fail on environments with and without `jsonschema` installed.

2) Severity: Med
- Evidence: `.harness/tools/abm_bench.py` `latest_run_done()` iterates `RUN_RECEIPTS_DIR.glob("*.json")` unsorted, and picks latest via `>=` on timestamp string.
- Why it matters (impact on complexity/coupling/maintainability): “Latest run” can vary by filesystem iteration order; benchmark results and limits can be nondeterministic.
- Smallest viable fix: Sort receipt paths by filename or parsed timestamp before selection.
- Effort: S
- Change risk: Low
- Suggested acceptance criteria: Given fixed receipts, `latest_run_done()` returns the same receipt across multiple runs and platforms.

3) Severity: Med
- Evidence: `.harness/tools/ralph.py` mixes orchestration policy, git commits, dispatch mutation, event emission, and receipt writing in a single module and function (`one_cycle`).
- Why it matters (impact on complexity/coupling/maintainability): Tight coupling complicates testing and changes; altering policy risks side effects to git/events/receipts.
- Smallest viable fix: Extract pure state-transition logic (selection, promotion decisions) into a separate module; keep IO in thin wrappers.
- Effort: M
- Change risk: Med
- Suggested acceptance criteria: Core transition logic is testable without filesystem or git; `ralph.py` remains a thin IO controller.

4) Severity: Med
- Evidence: `.harness/tools/receipt.py` `now_utc_z()` always uses real time; no override like `HARNESS_NOW_ISO` in `.harness/tools/util.py`.
- Why it matters (impact on complexity/coupling/maintainability): Receipt names and run IDs are time-variant; this complicates reproducibility and deterministic replay when running automated checks.
- Smallest viable fix: Add an env override for receipt timestamps consistent with `HARNESS_NOW_ISO`, or route time generation through `util.now_iso()`.
- Effort: S
- Change risk: Low
- Suggested acceptance criteria: With a fixed env time override, receipts and run IDs are repeatable.

5) Severity: Low
- Evidence: Threshold constants live in code (`.harness/tools/abm.py`) and separately in docs (`docs/INVARIANTS.md`) with no enforced linkage.
- Why it matters (impact on complexity/coupling/maintainability): Contract drift risk; docs can diverge from runtime behavior without a check.
- Smallest viable fix: Move thresholds into a single JSON/YAML contract (e.g., `contracts/limits.json`) and load in `abm.py`; verify in DoD.
- Effort: M
- Change risk: Low
- Suggested acceptance criteria: A DoD check fails if documented thresholds differ from runtime values.

6) Severity: Low
- Evidence: `.harness/tools/util.py` `run_cmd()` uses `shell=True` when a string is passed; `.harness/contracts/hooks.json` allows arbitrary commands.
- Why it matters (impact on complexity/coupling/maintainability): Increases risk of accidental shell injection and non-portable behaviors across environments; affects deterministic automation.
- Smallest viable fix: Enforce list-form commands internally and validate hooks to be list-form; keep `shell=True` only for explicitly trusted contexts.
- Effort: M
- Change risk: Med
- Suggested acceptance criteria: All internal calls to `run_cmd` pass list args; hooks validation rejects string commands.

**D) REFACTOR PLAN (phased)**

Phase 0: safe cleanups (no behavior change)
- Goals: Deterministic verification; remove nondeterminism in selection.
- Steps:
  - Make ABM event validation deterministic across environments by standardizing on one validator path (`.harness/tools/verify.py`).
  - Sort receipt glob ordering in `latest_run_done()` (`.harness/tools/abm_bench.py`).
- Affected files: `.harness/tools/verify.py`, `.harness/tools/abm_bench.py`.
- DoD checks to add/adjust: Add a check that runs `verify.py --check abm` with `jsonschema` both present and absent in CI (or enforce requirement).

Phase 1: boundary fixes (policy/mechanism separation)
- Goals: Reduce coupling and isolate side effects for testing.
- Steps:
  - Extract pure orchestration logic (WO selection, promotion decision) from `.harness/tools/ralph.py` into a separate module (e.g., `.harness/tools/ralph_core.py`).
  - Keep IO wrappers for git, receipts, events, and status writing in `ralph.py`.
- Affected files: `.harness/tools/ralph.py`, new module under `.harness/tools/`.
- DoD checks to add/adjust: Add a lightweight unit test or scripted check for deterministic selection given a fixed dispatch.

Phase 2: larger redesigns (only if justified)
- Goals: Centralize contracts to avoid drift and improve automation readiness.
- Steps:
  - Move guardrail thresholds and scaling limits into a contract file (e.g., `contracts/limits.json`).
  - Load contract values in `abm.py` and validate against `docs/INVARIANTS.md`.
- Affected files: `.harness/tools/abm.py`, `docs/INVARIANTS.md`, new contract file.
- DoD checks to add/adjust: Add a “contracts sync” check that compares doc values to runtime config.

**E) “DO NOT TOUCH (YET)” LIST**
- `receipts/` and receipt validation logic in `.harness/tools/verify.py` and `.harness/tools/receipt.py` — high risk without full test coverage.
- `.harness/contracts/dispatch.json` and related schema contracts — central to the harness; changes should be planned with migration steps.
- Event schema (`contracts/abm_event.schema.json`) — consumer contracts (ABM_UI and other tooling) likely rely on stability.
