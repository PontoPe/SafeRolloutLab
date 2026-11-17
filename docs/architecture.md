# Architecture and contracts

```text
separate finite loadgen process --HTTP/127.0.0.1--> API/router process
                                                    |
                                         deterministic SHA-256 bucket
                                           /                    \
                                stable lane                  candidate lane
                              worker supervisor             worker supervisor
                             1 active + 1 queued           1 active + 1 queued
                                    |                            |
                           short-lived regex child      short-lived regex child
                                    \                            /
                                       versioned metrics.jsonl

separate controller CLI process --> telemetry + route.json + decision journal
                                      |
                         lock/CAS -> fsync/atomic rename -> exact readback
```

## Rule pipeline

Schema and syntax validation (syntax compilation also in a child) → synthetic functional fixtures → bounded adversarial performance profile → canary 10%, 50%, 100% → promotion. The built-in policy blocks bodies consisting entirely of ASCII `a`; `stable`, `good` and `expensive` implement that toy policy, while `false-positive` searches for any `a` and blocks `account`. Version identifiers are SHA-256 of the canonical sorted JSON rule (including its name). Rules are in `src/saferollout/rules.py`; activated rules and gate outputs are persisted as JSON in the dedicated route file. This MVP does not import arbitrary rule files or accept rules through HTTP.

The intentionally weak `small` performance profile is an explicit fault experiment, never the default. It does not demonstrate that preflight guarantees safety. Default performance probe is 30 `a` characters followed by `!` in a resource-limited child. A successful single bounded performance probe is not a benchmark percentile or complete input-space proof.

## Resource envelope

- Request body ≤8,192 bytes, text ≤4,096 UTF-8 bytes, request ID ≤128 bytes, regex ≤256 characters.
- HTTP handlers ≤4, TCP backlog 8, accepted socket timeout 1 second. Excess accepted connections receive 503. Queues are finite, not buffered without limit.
- Each worker lane has one active child and one waiting request. Queue wait ≤120 ms, child wall deadline 120 ms; kill then `communicate()` waits/reaps. Thus queue+execution can approach 240 ms. Generic worker configurations are bounded at 4 active + 8 queued, deadline 30–500 ms; API uses the stricter envelope above.
- Child RLIMIT_CPU=1 second, RLIMIT_AS=96 MiB, RLIMIT_NOFILE=16, RLIMIT_NPROC=0, core dumps disabled. This is a regex-cost boundary, not a sandbox for arbitrary code. Linux `wait4` measures per-child user+system CPU, including interpreter startup; wall time includes startup and queue.
- JSONL file budget 16 MiB per journal. No request text is recorded in HTTP metrics. This is a finite run budget, not a production retention policy.
- Load is serial, ≤12,000 requests, ≤90 seconds per stage, HTTP timeout 2 seconds. Demo subprocess controls have 15-second timeout, load process 95 seconds, readiness 5 seconds; its full nominal maximum is bounded by baseline plus three load windows. API server itself is intentionally long-lived until its owner stops it.

## State and decisions

A single durable JSON document contains epoch, stable/original/candidate rules, percentage, stage, status, gate evidence, minimum sample and stage start. Writers serialize using a dedicated `flock` with 500 ms acquisition deadline; epoch compare-and-swap prevents stale writes/double promotion. Atomic same-directory replacement, file/directory fsync and exact readback precede a success return. Disk I/O itself is not preemptible by the in-process store; demo CLI calls have a separate process timeout.

For each current epoch, observations are separated by exact rule hash. Missing/malformed/duplicate telemetry or too few samples is INCONCLUSIVE. A candidate worker error/timeout/overload, incorrect blocking result or >250 ms observation can abort early. With sufficient samples, candidate p95 must be ≤max(50 ms, 2×stable p95); unexpected error growth must be ≤1 percentage point. The implementation is stricter than that relative error allowance: any candidate infrastructure error immediately aborts. Expected 403 blocks are not errors. p95 is nearest-rank; p99 is deliberately not produced.

Successful stages advance epoch and percentage; only the final stage updates stable. Each decision invocation reloads persisted state, and terminal-state replay is NOOP. Rollback restores the original rule and 0% candidate without contacting HTTP or rebuilding code. Recovery means route readback; in-flight requests retain their snapshotted epoch/rule and may still complete or time out. It does not mean old requests were retroactively canceled. A stale stage (120 seconds) is INCONCLUSIVE and attempts rollback when `observe` next runs. There is no independent expiration watchdog.

The 100% stage explicitly alternates a `/baseline` control request with candidate-routed requests. Loadgen keeps the same ordered fixture distribution separately per version; these are synthetic, controlled cohorts, not a model of natural traffic. Untrusted users must not have access to this loopback-only control probe or filesystem.
