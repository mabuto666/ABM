# Agentic Base Metrics (ABM)  
**Software Design Document (SDD)**

**Role perspective:** Senior Systems Architect & Product Designer  
**Mode:** Design & specification only  
**Audience:** Autonomous build system using ORC-base (MAYOR / WORKER / RALPH)

---

## 1. Purpose & Scope

### 1.1 Purpose

Agentic Base Metrics (ABM) defines a **foundational, reusable metrics and telemetry framework** for evaluating the performance, reliability, and scaling characteristics of agentic systems.

ABM exists to make agentic execution **measurable, comparable, and testable** without human interpretation, enabling:

- Deterministic evaluation of autonomy  
- Empirical comparison of orchestration strategies  
- Identification of scaling limits  
- Verification-driven operation (Definition of Done as a control primitive)

ABM is explicitly **not an observability product**. It is a **measurement substrate** designed to support experimentation, benchmarking, and automated verification.

---

### 1.2 Scope

ABM applies to agentic systems that exhibit one or more of the following properties:

- Multi-agent orchestration  
- Iterative execution loops (e.g. do-while-until-done)  
- Tool-calling automation  
- Verification-gated progress or halting  
- Autonomous task execution without human steering  

---

### 1.3 What ABM Is

- A metrics taxonomy  
- A conceptual data model  
- A deterministic emission lifecycle  
- A verification-aligned measurement contract  
- A stable design input for autonomous builders  

---

### 1.4 What ABM Is Not

- Not an agent framework  
- Not an orchestration engine  
- Not a logging library  
- Not a dashboarding system  
- Not a policy engine  
- Not vendor-specific  
- Not responsible for decision-making or remediation  

---

### 1.5 Intended Reuse Boundaries

ABM is designed to be reused:

- Across projects  
- Across execution models (single-agent → multi-agent)  
- Across LLMs and toolchains  
- Across environments (local, CI, cloud)  

ABM is **not** designed to be modified per project. Extensions must be additive and versioned.

---

## 2. Core Concepts & Definitions

### 2.1 Agent

An **Agent** is an autonomous execution unit that:

- Receives a bounded instruction or role  
- Performs computation, reasoning, or tool invocation  
- Emits measurable events  
- Does not own global system state  

Agents are not assumed to be intelligent, reliable, or stateful.

---

### 2.2 Work Order

A **Work Order** is the **atomic unit of intent**.

Properties:

- Immutable identifier  
- Explicit inputs  
- Explicit acceptance criteria  
- Deterministic completion conditions  
- Binary terminal state (done / not done)  

All metrics are attributable to a Work Order.

---

### 2.3 Execution Cycle

An **Execution Cycle** is a single pass through a do-while-until-done loop, including:

1. Selection of a ready Work Order  
2. Agent execution attempt(s)  
3. Verification  
4. State transition or retry  

Execution Cycles are countable, ordered, and bounded.

---

### 2.4 Verification

**Verification** is a deterministic evaluation that asserts whether acceptance criteria are met.

Verification must be:

- Machine-executable  
- Binary (pass / fail)  
- Side-effect free  
- Repeatable  

Verification gates progress.

---

### 2.5 Throughput vs Coordination Cost

- **Throughput:** rate of Work Orders reaching verified completion  
- **Coordination Cost:** overhead introduced by orchestration, dependencies, retries, and blocking  

These are treated as **independent measurable dimensions**.

---

## 3. System Boundaries

### 3.1 In Scope

ABM measures:

- Execution behavior  
- Coordination behavior  
- Verification behavior  
- Resource consumption attributable to autonomy  

---

### 3.2 Explicit Non-Goals

ABM does **not**:

- Optimize execution  
- Schedule agents  
- Resolve failures  
- Retry intelligently  
- Interpret task semantics  
- Decide correctness beyond declared verification  

ABM surfaces facts; it does not act on them.

---

## 4. Metrics Taxonomy

All metrics MUST be:

- Atomic  
- Numerically measurable  
- Time-bound  
- Attributable to a Work Order and Execution Cycle  

---

### 4.1 Execution Metrics

- Execution latency  
- Execution attempts  
- Execution success  
- Execution failure rate  
- Idle time  

---

### 4.2 Coordination Metrics

- Work-in-progress (WIP) count  
- Blocking time  
- Serial dependency depth  
- Parallelism factor  
- Coordination overhead  

---

### 4.3 Verification Metrics

- Verification pass / fail  
- Verification latency  
- Verification retries  
- Time-to-halt  
- False progress  

---

### 4.4 Cost Metrics

- LLM call count  
- Tool call count  
- Token consumption (if available)  
- Human touches  
- Cost per completion  

---

## 5. Data Model (Conceptual)

### 5.1 Core Entities

- Run  
- Work Order  
- Execution Cycle  
- Agent  
- Verification Result  
- Metric Event  

---

### 5.2 Relationships

- A Run contains many Work Orders  
- A Work Order has many Execution Cycles  
- An Execution Cycle emits many Metric Events  
- A Verification Result is associated with exactly one Execution Cycle  
- Metrics are never shared across Work Orders  

---

### 5.3 Mutability Rules

| Entity | Mutability |
|------|------------|
| Work Order | Immutable |
| Metric Event | Append-only |
| Execution Cycle | Append-only |
| Verification Result | Append-only |
| Aggregates | Derived only |

---

## 6. Lifecycle & Flow

### 6.1 Metric Emission During Ralph Loop

For each Execution Cycle:
1. Cycle start  
2. Execution attempt(s)  
3. Verification  
4. State transition  
5. Cycle end  

---

### 6.2 Aggregation

- Post-hoc only  
- Never influences execution  
- Frozen after terminal halt  

---

### 6.3 Finalization

A Run is finalized when:
- No ready Work Orders remain, or
- Deterministic halt condition is met

---

## 7. Verification & Definition of Done (ABM)

ABM is working when:
- All execution paths emit metrics
- Replays produce identical aggregates
- No silent execution exists

---

## 8. Extensibility Model

- Additive only
- Versioned
- No metric redefinition

---

## 9. Failure Modes & Guardrails

ABM must detect:
- Infinite loops
- Zero progress
- Verification deadlock
- Silent execution

ABM must not fix them.

---

## 10. Assumptions & Open Questions

Explicitly deferred:
- Cross-run normalization
- Statistical confidence
- Adversarial agents

---

**End of Software Design Document**
