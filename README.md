# SafeRollout Lab

**Can a functionally correct but computationally expensive security rule be rejected before promotion, and rolled back without the affected HTTP service?**

A bounded, local Python lab inspired by Cloudflare's [July 2, 2019 outage post-mortem](https://blog.cloudflare.com/details-of-the-cloudflare-outage-on-july-2-2019/). This is not a WAF, production deployment platform, or reproduction of Cloudflare's scale.

[![CI](https://github.com/PontoPe/SafeRolloutLab/actions/workflows/ci.yml/badge.svg)](https://github.com/PontoPe/SafeRolloutLab/actions/workflows/ci.yml)

## Run

Verified runtime: Linux, CPython **3.11.2**, pytest **7.2.1**, gitleaks **8.30.1**. Runtime has no third-party dependencies. No credentials or `.env` are needed. From a fresh checkout:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install 'pytest==7.2.1'
# Install gitleaks 8.30.1 separately; CI verifies the release archive checksum.
python3 -m pytest -q
./scripts/install-hooks.sh          # project-local Git hook, no commit
./scripts/secret-scan.sh all
./scripts/demo.sh .run/my-demo 100  # new directory; real loopback HTTP and subprocesses
```

The demo launches a loopback API, a separate bounded load-generator process, and a **new controller OS process per decision**. It exercises baseline, 10/50/100% promotion, functional rejection, performance rejection, canary timeout/rollback, missing telemetry, insufficient sample, controller restart/idempotence, API outage, deliberate control-lock failure, recovery and cleanup. It exits nonzero if its checked acceptance assertions fail. Its `summary.json`, raw `metrics.jsonl`, `client-*.jsonl`, commands and decision journal are the evidence; no benchmark data is synthesized.

**Calibration:** the controller defaults to **1,000 observations/version/stage**. The checked-in shared-host demonstration explicitly uses **100/version/stage**, finite serial load and a 90-second load budget. Integration tests use 10 as a smoke check, not as performance evidence. Nearest-rank p95 has only five tail observations at n=100; no p99/confidence claim is made. At 100% routed traffic, an explicitly separate `/baseline` control cohort preserves a concurrent stable comparison; it is not counted as routed exposure.

## Results and design

- [Measured technical case](docs/technical-case.md), [raw evidence index](docs/evidence/README.md).
- [Architecture and contracts](docs/architecture.md), [threat model](docs/threat-model.md).
- [Runbook / recovery / cleanup](docs/runbook.md), [learning missions](docs/learning-missions.md).

The good rule promotes and is read back. The expensive rule passes small functional cases but fails the default adversarial performance gate. Deliberately choosing the `small` preflight profile models a blind test suite: the same expensive rule reaches canary, times out in a killed/reaped resource-limited child, and the controller restores the known-good route. A false-positive rule is rejected by functional fixtures. Rollback under HTTP-process outage works through dedicated local state; deliberate lock contention yields **ROLLBACK_FAILED**, never a recovery claim — and a persisted halt latch stops further promotion from a restarted controller until explicit verified rollback, provided the sidecar could be persisted (or remains unreadable). Serialize controller commands: the halt check and route CAS are not one cross-controller transaction. See the [storage/concurrency limits](docs/delivery-report.md).

## Deliberate MVP boundaries

One HTTP frontend hosts two separately capacity-limited worker lanes; it is not two independent API hosts. The frontend and filesystem remain shared failure domains. Stopping the whole frontend proves control-plane independence but temporarily stops both traffic lanes until the process restarts. Native Linux execution was used: Docker daemon/Compose exist, but no Python base image is cached; no image pull/build/container/service mutation was performed. No Docker isolation or Compose result is claimed.

No daemonized automatic observer, dashboard, AWS, Kubernetes, public ports, real traffic or authentication system is included. `observe` must be invoked by the experiment/operator; its 120-second stage deadline is checked on observation, not an independent watchdog. The experiment cleans up all processes it starts.

## Demo and portfolio

- [Real terminal recording and replay instructions](docs/demo/README.md): tests, full HTTP experiment and measured failure outcomes. Re-record with `python3 scripts/record-demo.py`; no generated terminal output is substituted for command output.
- [Resume bullets and evidence map](docs/resume.md), [publication handoff](docs/publication.md).
- CI runs tests (including the bounded HTTP smoke experiment), compilation, directory and Git-history secret scanning. Actions are pinned by commit SHA, with read-only repository permission and no stored checkout credentials. It does not deploy or publish packages.

Start with learning mission 1: predict why the expensive rule passes small functional cases, then trace its actual preflight rejection and canary timeout in the recording. Explain why rollback still works while the HTTP frontend is stopped, and what that does not prove.
