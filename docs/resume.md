# Resume bullets and evidence map

Use only after personally reproducing the lab and being able to explain its limits. This is a portfolio project, not employment or a production deployment.

## Concise bullets

- Built a Python security-rule rollout lab with killable, resource-limited regex subprocesses, deterministic 10/50/100% canary stages and verified local rollback independent of the HTTP frontend.
- Exercised 23 automated tests and a recorded 1,510-observation HTTP experiment, demonstrating rejection of costly/false-positive rules, fail-closed canary timeouts and no promotion on missing telemetry.
- Added SHA-pinned, read-only GitHub Actions CI with reproducible tests and checksum-verified gitleaks directory/history scanning; documented rollback halt persistence and single-operator/storage limits.

## Evidence map

| Claim | Inspect/reproduce |
|---|---|
| Resource bounds and child kill/reap | `src/saferollout/worker.py`, `worker_child.py`, `tests/test_worker.py`, `tests/test_safety.py` |
| Staged routing and independent rollback | `controller.py`, `router.py`, `tests/test_controller.py`, `tests/test_canary.py` |
| 23 tests and actual experiment | [Recording/transcript](demo/README.md), [summary](demo/publication/evidence/summary.json), `scripts/demo.sh` |
| CI and secrets gates | `.github/workflows/ci.yml`, `scripts/ci.sh`, `scripts/secret-scan.sh`; [remote run list](https://github.com/PontoPe/SafeRolloutLab/actions/workflows/ci.yml) |
| Motivation | John Graham-Cumming, Cloudflare: [Details of the outage on July 2, 2019](https://blog.cloudflare.com/details-of-the-cloudflare-outage-on-july-2-2019/) |

## Interview explanation

Functional fixtures can approve an expensive rule on short inputs. The default bounded adversarial gate catches it before mutation; deliberately weakening the corpus demonstrates why a canary must still stop on real timeouts. HTTP 403 is an expected security decision, not automatically an availability failure. A controller result is not enough: rollback reads back the exact stable version and the demo makes a real request afterward.

Do not claim: production WAF, global/HA deployment, independent API hosts, distributed/multi-operator transaction safety, container isolation, continuous watchdog, high-load benchmark, production SLO improvement, Cloudflare integration, or arbitrary-code sandboxing. Local host/filesystem failures and an absent observer remain outside the guarantee.
