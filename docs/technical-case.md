# Technical case: costly security rules without a global rollout

## Question and hypothesis

Inspired by Cloudflare's [2019 post-mortem](https://blog.cloudflare.com/details-of-the-cloudflare-outage-on-july-2-2019/), this native Linux experiment asks whether functional correctness alone can miss an availability defect, and whether a separate local controller can reverse exposure while the HTTP process is unavailable. Hypothesis: bounded performance preflight rejects the pathological candidate, while a deliberately blind preflight is caught by a canary timeout and independent route rollback.

## Provenance and conditions

- Evidence run: `docs/evidence/native-mvp-03/` (after the rollback-latch fix; same stage counts and outcomes as the earlier `native-mvp-02`, which is kept as history).
- Python: 3.11.2; pytest 7.2.1; gitleaks 8.30.1. Native Linux, shared host. This historical run preceded publication; per-source SHA-256 values in its summary identify the runtime exactly. See [publication verification](publication.md) for the current repository/CI and recorded reexecution.
- All traffic is synthetic but all timings, HTTP responses and process results are real. Worker CPU includes interpreter startup; server elapsed includes queue/worker but excludes network. Client wall time is preserved separately. Load is serial to avoid stressing the shared host.
- The controller defaults to 1,000 observations/version/stage. This demonstration explicitly calibrates to 100/version/stage and 90-second load windows: enough to show the mechanism within a finite shared-host budget, not to prove production reliability. Integration tests use 10 solely for smoke coverage.
- Worker limits: 120 ms wall deadline, 1 CPU-second hard limit, 96 MiB address space, no core dumps, bounded children/queues, 4 KiB text. Generic malicious regex executes only in a disposable child.

## Actual stage measurements

Nearest-rank p95, current epoch only; milliseconds. The extra stable probe in the first stage is included transparently. At 100%, a separately labeled stable `/baseline` control cohort runs alongside 100% candidate-routed requests. It is not routed exposure.

| Routed stage | Stable n | Candidate n | Stable p95 ms | Candidate p95 ms | Gate |
|---|---:|---:|---:|---:|---|
| 10% | 973 | 100 | 15.377 | 15.447 | PASS |
| 50% | 113 | 100 | 15.945 | 15.918 | PASS |
| 100% | 100 | 100 | 16.300 | 14.047 | PASS |

All three good-rule stages passed; persisted stable version became `731bbac58cf784e1b4db033662aae315febc11b0147d410af3b03cf0012aeaea`. Each observation used a new controller OS process; terminal-state replay returned NOOP. Each candidate stage has only five observations in the upper 5% tail; no p99, confidence interval or production SLO claim is made. Functional fixtures are matched in distribution by version, but these small controlled cohorts do not represent natural traffic.

## Negative controls and recovery

| Scenario | Actual result |
|---|---|
| Good candidate | PROMOTED after 10/50/100% gates and exact route readback |
| Expensive candidate, small functional corpus | Functional PASS; correctness alone missed cost |
| Expensive candidate, default adversarial preflight | REJECTED before route mutation |
| False-positive candidate | Functional REJECTED; legitimate `account` must not be blocked |
| Deliberately weak `small` performance profile | Expensive rule entered 10% canary, then one real bounded adversarial request timed out |
| Same adversarial body on stable control | HTTP 200, 15.350 ms |
| Same body on candidate | HTTP 503, 120.848 ms; controlled timeout, fail closed |
| Canary failure | REJECT; route readback ROLLED_BACK in 5.533 ms |
| Actual request after rollback | HTTP 200, original stable hash |
| Missing telemetry / one insufficient sample | INCONCLUSIVE, no promotion |
| Entire HTTP process terminated | Independent controller rollback ROLLED_BACK in 5.640 ms; restarted HTTP request succeeded |
| Dedicated control-file lock held | ROLLBACK_FAILED (`control lock deadline`), no recovery claim; explicit retry after unlock succeeded |
| Same, then restart and feed passing samples (`docs/evidence/halt-cli-e2e/`, separate CLI processes) | Fresh `begin` and `observe` both returned HALTED; route stayed CANARY; explicit rollback restored it and reset the latch to READY |

The recovery milliseconds above measure local controller route mutation through readback, not timeout-to-full-service recovery. `commands.jsonl` and telemetry timestamps permit broader timing inspection. Requests already in flight are not retroactively canceled. Stopping the single frontend affects both lanes; only the control plane is independent of it.

## Totals and cleanup

The run recorded **1510** real inspection/control responses, **1** deliberate worker timeout, and **301** candidate-lane responses across stages and fault probes. Summed measured worker user+system CPU was **18657.715 ms**. These totals include baseline, stage traffic and recovery probes, not only candidate-routed traffic. Both API lifecycles were waited/reaped: `True`. Only project files/evidence remain. No shared container was started/stopped or other service changed.

## Limits and implementation choices

The native fallback was exercised, not Compose: Docker 29.9.2 and Compose v5.5.1 were discoverable, but no Python base image was cached, and no image was pulled or built. One HTTP frontend hosts separate bounded stable/candidate worker lanes; there are not two independently deployed APIs. Controller and data plane still share the host and local filesystem. State/CAS, fsync/readback and a control lock provide a local demonstration, not distributed control-plane resilience.

`observe` is an explicit CLI operation driven by the bounded experiment. It checks the 120-second stage deadline when invoked; no persistent watchdog is installed, and a stopped observer leaves the last route intact until observation/rollback resumes. Same-user filesystem tampering, host loss, disk failure, arbitrary untrusted code, remote attackers, production load, and full WAF semantics are outside scope. The weak preflight profile is intentionally selectable for the negative control and must not be mistaken for the default policy.

## Reproduce

```sh
python3 -m pytest -q
./scripts/secret-scan.sh all
./scripts/demo.sh .run/reproduce-01 100
```

See the [runbook](runbook.md), [threat model](threat-model.md) and [learning missions](learning-missions.md). `native-mvp-01` predates malformed-observation hardening; `native-mvp-02` predates the rollback halt-latch fix. Run `native-mvp-03` is authoritative for the runtime hashes behind the table above. The separately recorded publication reexecution is indexed in [demo evidence](demo/README.md); do not merge samples across runs.
