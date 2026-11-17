# Evidence index

## Authoritative final-source native run

`native-mvp-03/` contains the final-runtime-source real experiment after the rollback halt-latch fix. `native-mvp-02/` is historical and predates that fix:

- `summary.json`: run metadata, exact source SHA-256 values, all stage evaluations, expected fault outcomes and cleanup.
- `metrics.jsonl`: 1,510 actual server observations with rule hash, epoch, request ID, expected/matched decision, worker CPU, queue/wall latency, cohort and timestamp. Synthetic inputs, real measurements.
- `client-baseline.jsonl`, `client-stage-{10,50,100}.jsonl`: actual HTTP status, response and client timing.
- `commands.jsonl`: actual controller/loadgen command arguments, return codes, stdout/stderr and invocation timestamps. Paths refer only to this local project.
- `route.json` and `route.json.decisions.jsonl`: final persisted route and decisions. `route.json.lock` is an inert lock inode, not proof of a currently running owner.
- `ready-*.json`, `api-*.log`: dynamic loopback ports/PIDs and API lifecycle logs. Those processes are no longer running.

`native-mvp-01/` is the prior full run before the final malformed-observation guard; its recorded source hash identifies that difference. Do not mix its samples with run 02. Console JSON for each run is stored alongside its directory.

## TDD and safety controls

`tdd-01` through `tdd-15` paired RED/GREEN logs show incrementally exercised behavior slices: worker match/kill/reap, payload/capacity/CPU, rule gates, durable deterministic routing/CAS, metrics policy, controller state/recovery, live HTTP, canary failure, malformed metrics/lock deadline, request/queue/stage deadlines, full subprocess demo, budget/target/no-op-rule safety, newline policy equivalence, lane isolation and malformed JSON observations. Each GREEN file is a full-suite regression run at that step. RED 09 intentionally used an outer four-second `timeout` to demonstrate the missing control-lock deadline without hanging the host. Exit 124 is expected for that historical failing test, not an unexplained test runner failure.

`secret-hook-negative.txt` records rejection of a staged, randomly generated **synthetic** secret-like value; the fixture was unstaged and removed. It was not a real credential. `secret-hook-clean.txt` records a clean hook exit; `secret-scan-all.txt` records the complete directory scan. The exact source-hash-line allowlist in `.gitleaks.toml` addresses a measured false positive on the `src/saferollout/api.py` provenance hash, not an exclusion of source/evidence paths or real secrets. `verification.txt` is the final local CI/test/source-hash/process verification transcript.

The historical runs preceded publication, so their summaries use per-source hashes rather than a Git SHA. Current publication and exact-head CI are linked in [publication verification](../publication.md); the [recorded reexecution](../demo/README.md) preserves separate raw evidence. The source archive excludes `.git`, virtual environments, caches, live run directories, credentials and archives; it includes this evidence and `.env.example`. No API credential, `.env`, Docker socket, cloud resource or external service is needed to reproduce.
