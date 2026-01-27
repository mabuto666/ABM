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

## Smoke test (template)
```sh
python3 .harness/tools/new_project.py --name TESTPROJ --out /tmp/TESTPROJ
cd /tmp/TESTPROJ
python3 .harness/tools/doctor.py
python3 .harness/tools/verify.py
python3 .harness/tools/promptgen.py
```
