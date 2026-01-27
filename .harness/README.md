# Harness

This harness enforces a strict two-tier model: a Mayor orchestrator and stateless Workers. Workers receive only one Work Order (WO) at a time, execute it, and terminate. All truth comes from verification and receipts.

## Tools
- `doctor.py`: sanity checks for Python version, required paths, and git status.
- `verify.py`: validates dispatch invariants, receipts, scope guard, and project hooks; runs DoD checks.
- `promptgen.py`: emits exactly one Worker prompt for the next ready WO.
- `ralph.py`: orchestrates the Ralph do-while-until-done loop and writes status/receipts.

## Ralph Loop
Ralph repeatedly checks DoD, selects the next ready WO, runs acceptance, enforces scope, verifies, writes a receipt, and commits on success. It stops only when DoD passes.
