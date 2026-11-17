# Runbook

## Reproduce safely

From the repository root on Linux with Python 3.11 and pytest 7.2.1:

```sh
python3 -m pytest -q
./scripts/secret-scan.sh all
./scripts/demo.sh .run/reproduction-01 100
```

Use a new output directory each time; the demo refuses to overwrite one. Inspect `summary.json` for stage counts, p95, actual versions, failure decisions and cleanup. `metrics.jsonl` is server timing, `client-*.jsonl` contains actual HTTP status and end-to-end timing, `commands.jsonl` contains subprocess outputs, and `route.json.decisions.jsonl` records gate decisions. The Python runtime has no package-install step. Do not run in an Internet-facing environment. No Docker command is required.

`./scripts/ci.sh` runs the offline suite, compilation and gitleaks directory scan. Gitleaks is required and its absence is an error, not a skipped check. Reinstall the local hook after unpacking with `./scripts/install-hooks.sh`; the `.git` directory is excluded from delivery. The optional pre-commit config uses the same installed scanner. Hosted CI additionally scans Git history; see `.github/workflows/ci.yml`. It never deploys or publishes packages.

## Manual local session

```sh
export PYTHONPATH="$PWD/src"
mkdir -p .run/manual
python3 -m saferollout.controller --state .run/manual/route.json init
python3 -m saferollout.api --state .run/manual/route.json \
  --metrics .run/manual/metrics.jsonl --ready .run/manual/ready.json
```

Keep this API in its own foreground terminal. Read the dynamically assigned loopback port from `ready.json`. In another terminal (same PYTHONPATH), initialize a rule rollout:

```sh
python3 -m saferollout.controller --state .run/manual/route.json \
  --minimum 100 begin --rule good
python3 -m saferollout.loadgen --url http://127.0.0.1:PORT \
  --state .run/manual/route.json --output .run/manual/client-stage-10.jsonl --minimum 100
python3 -m saferollout.controller --state .run/manual/route.json \
  observe --metrics .run/manual/metrics.jsonl
```

Replace `PORT` with the ready-file integer. Repeat load+observe with a fresh client output file for 50% and 100%. The minimum selected by `begin` persists across controller restarts. Omitting `--minimum` selects 1,000; finite load/stage budgets can then produce INCONCLUSIVE instead of promotion, which is intentional. The 100-observation profile is a disclosed calibration, not the default policy.

## Recognize failures

- `REJECTED` at functional or performance preflight: route remains unchanged. Read gate observations, not only CLI return status.
- `INCONCLUSIVE`: no promotion. Check per-version counts/current epoch, telemetry types/duplicates, file budget and stage deadline. Obtain fresh comparable evidence, or explicitly roll back. No absent telemetry is interpreted as success.
- Canary `REJECT`: look for timeout, worker errors, false-positive mismatch, absolute deadline or p95 regression. The nested `rollback` result is authoritative for recovery, not the outer rejection alone.
- `ROLLBACK_FAILED`: progression is **latched off**. Before touching the route, rollback persists `route.json.safety.json` = `HALTED`; any later failure (lock deadline, lost state, readback mismatch) leaves it there, so every serialized `begin`/`observe` — including from a restarted controller process — returns `HALTED` instead of advancing, provided persistence succeeded (or the sidecar remains unreadable). Investigate the explicit error, then run an explicit `rollback`; only a verified restore whose audit record was also written sets the sidecar back to `READY`. The lab intentionally demonstrates a lock deadline failure.
- `audit_error`: the decision journal could not be written. Restoration still runs, but progression is latched `HALTED` until an operator rollback succeeds *and* is recorded. A passing stage whose decision could not be audited is not advanced (`route_unchanged: audit_failure`).
- `latch_error`: the halt sidecar itself could not be written. That controller process stays halted in memory; a new process reading an unreadable sidecar also fails closed. Fix the filesystem before recovering. If the sidecar could not be created at all and restoration also failed, a new process cannot recover the in-memory halt: do not restart/advance until an operator repairs storage and explicitly restores the route. Serialize all controller commands; halt checks and route CAS do not form a cross-controller transaction.

## Recover without HTTP

```sh
python3 -m saferollout.controller --state .run/manual/route.json rollback
python3 -m saferollout.controller --state .run/manual/route.json state
```

Expect `ROLLED_BACK`, percentage 0, candidate null, exact original stable hash. This works with the API process stopped. After restarting the frontend, make an actual `/inspect` request to prove service behavior; state readback alone is not a healthy-service claim. A rollback lock error can be retried only after the owning process releases its lock. Never delete a live process's lock file to bypass serialization. With corrupt/lost state, stop and restore a known reviewed snapshot; do not invent the original rule.

## Cleanup

The automated demo owns its child processes, terminates/waits for both API lifecycles in `finally`, and records `cleanup.api_reaped`. Requests finish before demo API termination. It leaves only evidence files and no installed services, containers or fixed ports. The foreground manual API is stopped with Ctrl-C in its own terminal, which closes the server and joins handlers; in-flight child deadlines bound remaining work. Do not `pkill python`, stop shared containers, or delete unrelated paths. Keep evidence until reviewed; deletion of a specific `.run/<your-run>` directory is optional and manual.

No broad kill or destructive cleanup script is supplied: the self-contained demo's owner performs lifecycle cleanup, and evidence preservation is deliberate.
