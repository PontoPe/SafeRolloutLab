# Case study: rolling out a costly security rule without trusting the failing service

This is the narrative version of the project. Measured numbers live in the [technical case](technical-case.md); raw files are indexed in [evidence/README.md](evidence/README.md). Everything below can be checked against code, tests or recorded evidence in this repository.

## 1. Problem

Cloudflare's [July 2, 2019 post-mortem](https://blog.cloudflare.com/details-of-the-cloudflare-outage-on-july-2-2019/) (John Graham-Cumming) describes a WAF rule whose regular expression backtracked catastrophically. The new rule was deployed everywhere at once and exhausted CPU on the machines that served traffic. Three lessons from that write-up motivate this lab:

1. A rule can be *correct* and still be *too expensive*; functional tests do not measure cost.
2. A global rollout turns one bad rule into a global incident; a staged rollout limits exposure.
3. Recovery should not depend on the system that is failing.

The question the lab asks: **can a functionally correct but computationally expensive rule be rejected before promotion, and rolled back without depending on the HTTP service it affects?**

Scope was fixed up front: one Linux host, one trusted operator, synthetic traffic, loopback only, standard-library Python. Not a WAF and not a production system.

## 2. Design decisions

| Decision | Why | Where |
|---|---|---|
| Evaluate regexes in a short-lived child process with `RLIMIT_CPU`, `RLIMIT_AS`, `RLIMIT_NOFILE`, `RLIMIT_NPROC` and a wall-clock deadline, then kill and reap | A thread timeout cannot safely interrupt Python's `re`; only process termination stops a stuck match | `src/saferollout/worker.py`, `worker_child.py`, `tests/test_worker.py`, `tests/test_bounds.py` |
| Separate functional and performance gates before any route change | Shows directly that "correct" ≠ "cheap": `expensive` passes the functional fixtures and fails the adversarial cost probe | `src/saferollout/rules.py`, `tests/test_rules.py` |
| Keep a deliberately weak `small` performance profile, never the default | Models a blind test suite so the canary path can be exercised with a rule that slips through preflight | `rules.py` (`performance_gate`), demo step `--profile small` |
| Deterministic SHA-256 bucketing of request IDs, stages 10% → 50% → 100% | Reproducible routing; exposure grows only after evidence | `src/saferollout/router.py` (`choose`), `tests/test_router.py` |
| Separate stable and candidate worker lanes, each with its own capacity and bounded queue | A slow candidate must not starve stable (production-like) traffic | `src/saferollout/api.py`, `tests/test_lane_isolation.py` |
| Rule version = SHA-256 of the canonical rule JSON; every response and metric carries version and epoch | Proves which rule actually served each request | `rules.py` (`version`), `tests/test_api.py` |
| Missing, malformed, duplicate or too-small telemetry → `INCONCLUSIVE` | Silence must never look like success | `src/saferollout/metrics.py`, `tests/test_metrics.py`, `tests/test_hardening.py`, `tests/test_observation_schema.py` |
| Expected 403 blocks are not availability errors; any candidate timeout/worker error aborts | Separates security decisions from infrastructure failures | `metrics.py` (`assess`) |
| Control plane = one local route file with `flock` (500 ms deadline), epoch compare-and-swap, fsync, atomic rename and exact readback, driven by a separate CLI process | Rollback must work while the HTTP process is down; stale controllers must not double-promote | `router.py`, `controller.py`, `tests/test_controller.py`, `tests/test_deadlines.py` |
| Rollback reports `ROLLED_BACK` only after readback; otherwise `ROLLBACK_FAILED` | An attempted rollback is not a recovery | `controller.py` (`rollback`), `tests/test_hardening.py` |

Things that were proposed but deliberately not built: Docker Compose (native Linux fallback used; no image was pulled or built), a persistent watchdog, multiple independent API hosts, and any external integration.

## 3. What the experiment showed

From the authoritative run `docs/evidence/native-mvp-03/` (details and figures in the [technical case](technical-case.md)) and the [recorded demo](demo/README.md):

- `good` passed 10/50/100% and was promoted; replaying the terminal state returned `NOOP`.
- `expensive` passed the functional fixtures but was rejected by the default performance gate, before the route changed.
- `false-positive` was rejected by the functional gate (it blocks `account`).
- With the weak `small` profile, `expensive` entered the 10% canary. The same adversarial body returned HTTP 200 on stable and HTTP 503 after the 120 ms deadline on the candidate. The controller decided `REJECT`, rolled back, and a real request afterwards returned 200 with the original stable hash.
- Missing telemetry and an insufficient sample were `INCONCLUSIVE`.
- With the API process terminated, controller rollback returned `ROLLED_BACK`; the restarted API served the stable rule.
- With the control lock deliberately held, rollback returned `ROLLBACK_FAILED`; an explicit retry after unlock succeeded.

## 4. The defect: a failed rollback could still lead to promotion

**Symptom.** Rollback is the safety action, so its failure path matters most. Consider the final stage: a candidate is at 100% and the operator (or a `REJECT` decision) triggers rollback, but the rollback cannot complete, for example because the control lock is held. Before the fix, the route stayed at `CANARY` 100%, and nothing recorded that progression had to stop. A **new** controller process that was then fed passing samples evaluated them normally and returned `PASS`, which at stage 2 promotes the candidate to stable. A rollout that had been ordered back was pushed forward instead.

**RED evidence.** `docs/evidence/halt-01-red.txt` is the failing run of `test_failed_final_stage_rollback_halts_across_restart_until_recovery`:

```text
>       assert c.observe(passing)['decision'] == 'HALTED'
E       AssertionError: assert 'PASS' == 'HALTED'
```

A related gap, `docs/evidence/halt-02-red.txt`: when the decision journal could not be written, `observe` crashed with `IsADirectoryError` instead of still restoring the stable rule.

**Fix** (`src/saferollout/controller.py`):

- `rollback()` writes a persisted halt latch, `route.json.safety.json` = `HALTED`, **before** touching the route. Any later failure (lock deadline, lost state, readback mismatch) leaves the latch in place.
- `begin()` and `observe()` check the latch first and return `HALTED` instead of acting, including in a freshly started controller process.
- The latch is set back to `READY` only after a restore that was verified by readback **and** recorded in the audit journal.
- If the journal cannot be written, restoration still runs, the controller latches, and an unaudited `PASS` is not applied (`route_unchanged: audit_failure`).
- If the latch file itself cannot be written, the current process stays halted in memory, and a new process that finds an unreadable sidecar also fails closed.
- `_latch()` never raises, so a latch failure cannot block restoration.

**Regression tests** (`tests/test_controller.py`), all part of the 23-test suite run in CI and shown by name in the demo:

- `test_failed_final_stage_rollback_halts_across_restart_until_recovery`: held lock → `ROLLBACK_FAILED`; a new controller returns `HALTED` for both `observe` and `begin`, the route is unchanged; explicit rollback succeeds and a new rollout can begin.
- `test_audit_failure_still_restores_and_requires_explicit_recovery`: unwritable journal → `REJECT` with `audit_error`, route still restored; progression stays `HALTED` until a rollback that is both verified and recorded.
- `test_unwritable_halt_latch_still_restores_and_halts_in_process`: latch cannot persist → route restored with `latch_error`, this process and a fresh process both stay `HALTED`.

GREEN logs: `docs/evidence/halt-01-green.txt`, `halt-02-green.txt`. An end-to-end check with separate CLI processes is recorded in `docs/evidence/halt-cli-e2e/`: fresh `begin` and `observe` returned `HALTED`, the route stayed `CANARY`, and explicit rollback restored it and reset the latch to `READY`.

**Residual limit of the fix.** It is restart-safe only if the latch was persisted (or the sidecar is unreadable). If storage prevents creating it at all *and* rollback fails, only the current process remembers the halt. Controller commands must also be serialized: the halt check and the route compare-and-swap are not one atomic transaction across overlapping controllers.

## 5. Limits

- No Docker/Compose; no container isolation claimed.
- No high availability: one HTTP frontend serves both lanes; controller, data plane and state share one host and filesystem.
- No watchdog: `observe` runs only when invoked; the 120-second stage deadline is checked at observation time.
- Single trusted operator; same-user filesystem tampering is out of scope.
- Synthetic, serial, loopback traffic. The demo uses 100 observations/version/stage (default 1,000); nearest-rank p95 only, no p99, no SLO or capacity claim.
- Resource limits bound this regex workload; they are not an arbitrary-code sandbox.

Full list: [delivery report](delivery-report.md), [threat model](threat-model.md), [publication notes](publication.md).

## 6. Next steps

Not implemented; candidates for future work, each needing its own evidence before being claimed:

1. Run the same experiment under Docker Compose with cgroup CPU/memory/PID limits, as originally proposed, and compare to the native results.
2. Make the halt check and route update a single locked transaction so overlapping controllers are safe.
3. Add a scheduled observer with its own deadline, and test what happens when it dies.
4. Split stable and candidate into separately deployed API processes so a frontend crash does not stop both lanes.
5. Collect enough samples (the default 1,000 per stage or more) to report p99 honestly.
6. Compare the backtracking `re` worker with a linear-time engine such as RE2.
