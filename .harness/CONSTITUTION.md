# Harness Constitution

## Doctrine
- Two-tier hierarchy only: Mayor -> Worker.
- No peer coordination between workers.
- Workers are ignorant by construction; only minimum viable context is provided.
- No shared state between workers.
- Episodic execution: a worker runs one Work Order (WO) and terminates.
- Verification and receipts are the only source of truth.
- The Definition of Done (DoD) is the only stop condition.
- Complexity belongs in orchestration, not in agents.

## Anti-Patterns (Explicitly Forbidden)
- Flat teams or peer worker meshes.
- Shared memory or shared mutable state across workers.
- Long-running workers or multi-episode agents.
- Worker-to-worker negotiation or coordination.
- Hidden state or implicit completion criteria.
- Skipping receipts or bypassing verification.
