# Historical delivery report — local MVP before publication

This report records the earlier local handoff. Statements below about no commit/push/hosted CI were true at that handoff, not the present publication state. See [publication verification](publication.md) for the subsequent work; runtime limitations below remain applicable.

## Verified artifact

Project root: `/home/pontope/Coding/saferollout-lab`.

- `python3 -m pytest -q`: **23 passed** after the rollback-latch fix; parent reexecution **9.62 s**. Includes real HTTP, bounded malicious regex children, restart/CAS, independent rollback and full process demo. Regression tests include persistent halt after failed rollback, audit-failure restoration and an unreadable halt sidecar.
- `./scripts/ci.sh`: tests, Python compilation and gitleaks directory scan all passed. Gitleaks 8.30.1 is installed on the host; it is not vendored in the delivery.
- Explicit negative staged-secret hook check rejected a randomly generated synthetic secret-like value with exit 1. The fixture was unstaged and deleted. Clean staged hook and full directory scan passed.
- `PYTHONPATH=src python3 -m saferollout.demo --output .run/post-fix-review --minimum 100` (preserved at `docs/evidence/native-mvp-03/`): real complete experiment, **1,510 server observations**, **1 intentional timeout**, good rule promoted at 10/50/100%, bad preflight candidates rejected, weak-profile canary defect rolled back, missing/small telemetry inconclusive, HTTP-process-down rollback confirmed, intentional control-lock failure reported as ROLLBACK_FAILED then recovered after unlocking.
- Final source provenance: all **9 Python source hashes** match `docs/evidence/native-mvp-03/summary.json`; its recorded API PIDs are absent. Earlier `native-mvp-02` and `verification-state.json` are historical, pre-fix records.
- Parent additionally exercised the CLI in separate processes under a held lock: failure persisted HALTED, fresh begin/observe stayed HALTED, and explicit rollback restored the route and READY latch.
- No commit, push, publication, external notification, credentials, `.env`, AWS, production or shared-service/container changes. Git was initialized only for the local pre-commit hook; files are uncommitted.

## Main files

`src/saferollout/`: bounded subprocess worker/child, rules and gates, atomic deterministic router/store, HTTP API, persisted controller CLI, serial load generator, executable experiment. `tests/`: 23 test cases. `scripts/`: demo, local CI, secret scan and hook installation. `docs/`: architecture, threat model, runbook, technical case, learning missions and raw evidence. Root contains README, pyproject, ignore/example and scanner/hook configuration.

## Scoped deviations and blockers

- Native Linux fallback was exercised. Docker/Compose discovery succeeded, but no Python image was locally cached; no image pull, build or Compose execution occurred. No Dockerfile/Compose scaffold is presented as tested functionality.
- One HTTP frontend, two independently capacity-limited worker lanes, separate short-lived regex processes, separate controller process. This is not two independently deployed APIs or host-level fault isolation. Stopping the frontend affects both lanes until restart; controller route rollback still works.
- Controller default is 1,000 observations/version/stage; demonstration calibration is explicitly 100, tests 10. Only measured nearest-rank p95 is shown; no p99/statistical-strength claim. Load and stage time budgets may make the default larger sample inconclusive.
- `observe` is run by the finite experiment/operator. The 120-second stage budget is enforced on observation, not by an installed persistent watchdog. No background service remains.
- Final independent review passed for a single-operator, trusted-local lab. Serialize controller commands: the halt check and route CAS are not one transaction across overlapping controllers. Restart safety also requires that the halt sidecar was persisted or remains unreadable; if storage prevents creating it at all and route restoration fails, only the current process retains the in-memory halt. This is not a storage-failure-resilient or multi-operator controller.
- An attempted new project `AGENTS.md` write was blocked by the tool's protected-file approval timeout. It was not retried, bypassed or created. This did not prevent implementing or exercising the runtime acceptance criteria.
- No hosted CI workflow was enabled. `scripts/ci.sh` is the verified local/CI entrypoint, and `.pre-commit-config.yaml` plus an installed local Git hook use the real scanner.

## Delivery archive

Safe source/evidence archive: `dist/saferollout-lab-mvp-v3.tar.gz` (final parent-reviewed delivery; earlier archives are historical). Exclusions: `.git`, `.venv`, caches/bytecode, `.run`, `dist`, archives, all `.env` variants except the safe `.env.example`. No credential directory is included. Extract it into a new directory, rerun tests, and run `scripts/install-hooks.sh` to install a fresh local hook if desired.

Independent reviewer should rerun tests and `./scripts/demo.sh .run/independent-review 100`, inspect actual source/limits and compare the new raw evidence. Notifications/delivery are intentionally left to the parent after independent verification.
