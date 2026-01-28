# ABM + ABM_UI Architecture

ABM is a **measurement substrate** for agentic automation. ABM_UI is a **standalone, reusable consumer** that visualizes ABM (or other) telemetry via adapters. Together they form a closed loop: **execute → measure → export → consume → verify**.

---

## 1. Components

### 1.1 ABM (Agentic Base Metrics)
**Role:** Produce deterministic telemetry and benchmark outcomes for agentic execution.

**Key responsibilities**
- Define the measurement contract (SDD + invariants).
- Emit **append-only** event logs during execution cycles.
- Produce **derived-only** aggregates and scaling indicators.
- Provide deterministic benchmark suite + limit classification.
- Enforce correctness via **DoD (Definition of Done)** checks.

**Non-goals**
- Not an orchestration engine (Ralph controls execution).
- Not a logging library.
- Not an observability/dashboard product.

### 1.2 ORC-base Harness (embedded in ABM as `.harness/`)
**Role:** Deterministic execution harness + audit ledger.

**Key responsibilities**
- Ralph do-while-until-done loop (`ralph.py --loop`).
- Verification modes (`verify.py --check schema|work|dod`).
- Deterministic, append-only receipts ledger (audit trail).
- WIP=1 enforcement + dependency ordering.

### 1.3 ABM_UI
**Role:** Standalone telemetry consumer UI with pluggable adapters.

**Key responsibilities**
- Load telemetry datasets via adapter interface.
- Render scaling limits, tables, and raw record drilldown.
- Support ABM filesystem dataset contract (`/data`).
- Prove reuse via at least one non-ABM adapter (`/data_generic`).

**Non-goals**
- Not coupled to ABM internals.
- No requirement for ABM to embed UI logic.
- No runtime influence on ABM execution.

---

## 2. Data Contracts

### 2.1 ABM Event Log
**Format:** JSON Lines (`events.jsonl`)  
**Rule:** Append-only; never mutated or deleted.

Contains per-cycle facts such as:
- cycle start/end
- execution attempts
- verification results
- guardrail signals (deadlock, zero progress, etc.)

### 2.2 ABM Aggregates
**Format:** JSON (`aggregates.json`)  
**Rule:** Derived-only; post-hoc computation from events.

Includes:
- throughput
- coordination cost indicators
- verification drag indicators
- retry amplification indicators
- limit classification signals (as derived outputs)

### 2.3 Benchmark Results
**Format:** JSON (`results.json`)  
One record per (benchmark, parameter set), e.g. WIP sweep, dependency depth, verification drag, retry amplification.

### 2.4 ABM_UI Dataset Contract (Filesystem Adapter)
ABM_UI reads a served folder (default `/data`) containing:
- `results.json`
- `aggregates.json`
- optional `events.jsonl`

ABM exports this bundle via a dedicated tool:
- `tools/export_ui_bundle.py` (and helper shell script)

This contract is intentionally minimal and portable.

---

## 3. Execution and Measurement Flow

### 3.1 Golden Path (ABM)
1. **Dispatch** defines work orders and dependencies.
2. **Ralph loop** selects the next ready WO (WIP=1).
3. Execution occurs (agent/tool work).
4. **Verification** runs deterministically.
5. ABM emits events per execution cycle.
6. Work order transitions to done only when verified.

Terminal condition:
- exactly one `RUN_DONE` receipt when no ready work remains.

### 3.2 Benchmark Path (Phase 4)
1. Benchmark specs define parameter sweeps deterministically.
2. Runner executes a run per parameter set.
3. ABM aggregates compute scaling indicators.
4. Limit classification produces deterministic halt/degradation signals.
5. Results are written to `results.json` plus limit artifacts.

### 3.3 UI Consumption Path
1. ABM exports UI bundle:
   - `python3 tools/export_ui_bundle.py --out ../ABM_UI/web/data`
2. ABM_UI serves static UI:
   - `./demo.sh`
3. ABM_UI loads `/data/results.json` etc. via ABM filesystem adapter.

---

## 4. Verification and Guardrails

### 4.1 DoD as Control Primitive
ABM correctness is enforced by DoD checks:
- schema invariants
- receipts invariants
- project invariants
- no_ready_undone

DoD gates terminal completion; it does not interpret task semantics beyond declared checks.

### 4.2 Receipts Ledger
Receipts are an append-only audit ledger of:
- work order lifecycle receipts (e.g., COMPLETE)
- terminal run receipt (`RUN_DONE`)
- dispatch snapshot references

Receipts provide provenance and determinism of execution.

---

## 5. CI Closed-Loop Proof (recommended pattern)
A full closed-loop proof in CI should:
1. Run ABM DoD checks.
2. Export ABM UI bundle into ABM_UI.
3. Start ABM_UI static server.
4. Smoke-fetch `/data/results.json` and ensure parseable output.

This proves:
- ABM produces consumable artifacts
- the filesystem contract holds
- ABM_UI consumes the artifacts without coupling

---

## 6. Reuse Model

### 6.1 ABM Reuse
ABM is reused by:
- running its benchmark suite against different orchestrators/LLMs
- comparing scaling limit curves
- extending metrics additively (versioned)

### 6.2 ABM_UI Reuse
ABM_UI is reused by:
- implementing new adapters for other telemetry sources (files, HTTP, services)
- mapping arbitrary results/limits records into the UI’s normalized display schema

ABM is just one adapter, not a dependency.

---

## 7. Repository Structure (conceptual)

### ABM
- `.harness/` — ORC-base harness (Ralph, verify, receipts invariants)
- `contracts/dispatch.json` — work orders and dependencies
- `artifacts/abm/` — events, aggregates, benchmark results (canonical outputs)
- `tools/export_ui_bundle.py` — UI bundle exporter
- `docs/` — SDD + lifecycle + invariants + status

### ABM_UI
- `web/` — static UI (index.html, app.js)
- `web/adapters/` — adapter contract + ABM + generic adapters
- `web/data/` — optional sample dataset
- `web/data_generic/` — non-ABM sample dataset proving reuse

---

## 8. “Finished” Definition
ABM + ABM_UI is considered complete when:
- ABM produces deterministic `events.jsonl`, `aggregates.json`, `results.json`
- ABM DoD passes with a single terminal `RUN_DONE`
- ABM exports a stable UI bundle consumable by ABM_UI
- ABM_UI consumes ABM bundle and at least one non-ABM dataset via adapters
- (optional but strong) CI runs the full closed-loop smoke proof
