# ORC-base

Baseline Mayor/Worker harness template for clone-and-go projects.

## Create a new project
```sh
python3 .harness/tools/new_project.py --name <PROJECT_NAME> --out <DEST_PATH>
```

## Model
This harness enforces a strict two-tier hierarchy: a Mayor orchestrates, Workers execute a single WO and terminate. Ralph runs a do-while-until-done loop driven by verification and receipts.

## Quickstart (baseline repo)
```sh
python3 .harness/tools/doctor.py
python3 .harness/tools/verify.py
python3 .harness/tools/promptgen.py
python3 .harness/tools/ralph.py --loop
```

## Deterministic run bundles
```sh
ORC_NOW_ISO="2026-01-29T09:30:00+10:00" task verify
ORC_NOW_ISO="2026-01-29T09:30:00+10:00" task ralph
```

## Smoke test (template)
```sh
python3 .harness/tools/new_project.py --name TESTPROJ --out /tmp/TESTPROJ
cd /tmp/TESTPROJ
python3 .harness/tools/doctor.py
python3 .harness/tools/verify.py
python3 .harness/tools/promptgen.py
```

## Documentation
- **Code audit:** [CODE_AUDIT.MD](CODE_AUDIT.MD)
- **Architecture:** [ARCHITECTURE.md](ARCHITECTURE.md)
- **Testing guide:** [docs/README.md#testing](docs/README.md#testing)

## Architecture & ADRs
- [Baseline Review Process (ABM)](docs/adr/REVIEW_PROCESS.md)
- [Documentation index](docs/README.md)
- Harness provenance and upgrade policy: [docs/HARNESS_UPSTREAM.md](docs/HARNESS_UPSTREAM.md)
