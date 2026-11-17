# CV bullets and evidence map

Personal portfolio project, not employment and not a production deployment. Use these only after reproducing the lab yourself (see the [learning mission](learning-mission.md)) and being able to explain its limits. Every number below is a count taken from the repository, not a performance metric.

## Bullets

1. Built a Python lab for staged rollout of security rules, inspired by Cloudflare's 2019 regex outage: candidate rules pass functional and adversarial-cost gates, then a deterministic 10/50/100% canary, with rollback to the known-good rule confirmed by state readback.
2. Isolated regex evaluation in killable, resource-limited child processes (CPU, memory, file-descriptor and process limits plus a wall-clock deadline), and gave stable and candidate rules separate bounded worker lanes so a slow candidate fails closed with HTTP 503 without taking stable capacity.
3. Designed a file-based control plane separate from the HTTP service (lock with deadline, epoch compare-and-swap, fsync, atomic rename, readback), so rollback works with the API process stopped; missing or malformed telemetry is treated as inconclusive, never as a pass.
4. Fixed a safety defect where a failed rollback could still let a restarted controller promote the candidate: added a persisted halt latch and three regression tests, with RED/GREEN test logs kept as evidence.
5. Set up GitHub Actions CI with SHA-pinned actions and a read-only token, running a 23-test suite (including a real loopback HTTP experiment) and checksum-verified gitleaks scans of the working tree and full Git history; published an unedited terminal recording of the full experiment.

## Evidence map

| # | Claim | Where to verify |
|---|---|---|
| 1 | Gates, staged canary, readback | `src/saferollout/rules.py` (`functional_gate`, `performance_gate`), `src/saferollout/controller.py` (`STAGES`, `observe`, `rollback`), `tests/test_rules.py`, `tests/test_controller.py`, `tests/test_canary.py` |
| 1 | Inspiration | John Graham-Cumming, Cloudflare: [Details of the Cloudflare outage on July 2, 2019](https://blog.cloudflare.com/details-of-the-cloudflare-outage-on-july-2-2019/) |
| 2 | Child limits, kill and reap | `src/saferollout/worker.py`, `src/saferollout/worker_child.py`, `tests/test_worker.py`, `tests/test_bounds.py` |
| 2 | Separate lanes, 503 on candidate | `src/saferollout/api.py`, `tests/test_lane_isolation.py`; stable 200 vs candidate 503 on the same body in the [technical case](technical-case.md) |
| 3 | Control plane, CAS, readback | `src/saferollout/router.py` (`Store`), `tests/test_router.py`, `tests/test_hardening.py` (lock deadline) |
| 3 | Rollback without HTTP | `tests/test_controller.py::test_controller_rollback_independent_and_failure_is_honest`; `api_down_rollback` in `src/saferollout/demo.py` |
| 3 | Inconclusive on bad telemetry | `src/saferollout/metrics.py` (`assess`), `tests/test_metrics.py`, `tests/test_observation_schema.py` |
| 4 | Halt latch and regressions | `controller.py` (`_halted`, `_latch`, `rollback`); the three halt/audit tests in `tests/test_controller.py`; `docs/evidence/halt-0{1,2}-{red,green}.txt`, `docs/evidence/halt-cli-e2e/`; [case study §4](case-study.md#4-the-defect-a-failed-rollback-could-still-lead-to-promotion) |
| 5 | CI | `.github/workflows/ci.yml`, `scripts/ci.sh`, `scripts/secret-scan.sh`; [CI runs](https://github.com/PontoPe/SafeRolloutLab/actions/workflows/ci.yml) |
| 5 | 23 tests, 1,510 observations, recording | `python -m pytest -q`; [demo](demo/README.md), `docs/demo/saferollout-demo-summary.json` |

## Do not claim

Production WAF; Docker or container isolation; high availability, independent API hosts or multi-region; a watchdog or continuous monitoring; multi-operator or distributed transaction safety; load or capacity benchmarks; latency or SLO improvements; any Cloudflare integration; sandboxing of arbitrary code. Host, disk and filesystem failures and an absent observer are outside the guarantee.

## 30-second interview explanation

Functional tests can approve an expensive regex because short inputs never trigger the backtracking. A bounded adversarial cost probe catches it before any traffic moves. When the probe is deliberately weakened, the canary catches it instead: the candidate times out in its own lane, the controller rolls back, and recovery is confirmed by reading the route back and sending a real request. Rollback runs from a separate process against a local state file, so it still works when the API is down. When rollback itself fails, the system says so and stays halted, even after a restart; that guarantee came from fixing a real defect, covered by regression tests. An expected 403 is a security decision, not an availability error.
