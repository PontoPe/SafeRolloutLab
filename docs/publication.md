# Publication handoff

Repository: https://github.com/PontoPe/SafeRolloutLab

Scope: resume-ready native Linux portfolio lab, not a production deployment. This publication preserves the existing remote README history (`30e4af24d4366b81b8e23bb0c147b37f5a9d8336`) rather than replacing it. All nine runtime Python modules are unchanged from the reviewed `native-mvp-03` implementation, including the rollback halt-latch regression fixes.

## Verification and evidence

- Independent read-only runtime review: no blocking findings within trusted serialized single-operator scope; reviewer reran 23 tests successfully. Publication-facing docs now explicitly qualify halt persistence and controller serialization.
- Parent rerun: 23 tests passed; `scripts/ci.sh` passed tests, compilation and full-directory gitleaks 8.30.1 scan. Exact command output for tests and the full experiment is in the [real terminal recording](demo/README.md).
- Recorded reexecution: 1,510 observations; 10/50/100% good-rule PASS; false-positive/expensive default preflight REJECTED; blind-profile canary timeout and rollback; missing/insufficient telemetry INCONCLUSIVE; HTTP-down rollback; intentional lock failure; explicit recovery; cleanup confirmed. Summary source hashes match the checkout.
- CI definition: `.github/workflows/ci.yml`; Python 3.11, pytest 7.2.1, checkout/setup-python pinned by SHA, read-only `contents`, no credential persistence. Gitleaks 8.30.1 is downloaded from its official release and verified against a fixed SHA-256. Directory and complete Git history are scanned. No deployment, cloud secrets, signing or package publication permissions.
- Remote CI is a separate gate: use the [CI run list](https://github.com/PontoPe/SafeRolloutLab/actions/workflows/ci.yml) and compare `headSha` to the current remote main. The task handoff records the verified publication SHA and successful exact-head run URL; this file does not self-certify a future workflow result.

## Reproduce from a clean checkout

Follow the README virtual-environment steps, install gitleaks 8.30.1, run `./scripts/ci.sh`, then `./scripts/demo.sh .run/your-new-run 100`. No `.env`, credentials, Docker, registry, AWS or Kubernetes is needed. The GitHub source archive and checkout contain the same evidence; generated archives, `.run`, caches and virtual environments are ignored.

## Limits that still apply

- One frontend with two bounded worker lanes, shared host/filesystem; no HA or container deployment claim.
- Finite serial synthetic traffic, explicit 100/version/stage demonstration calibration versus default 1,000; p95 only, no production confidence/SLO inference.
- Explicit `observe`, not a continuous watchdog. Stopping observation leaves the last route active until observation/rollback resumes.
- Serialize controller commands. Halt checks and route CAS are not a cross-controller transaction.
- Restart halt safety requires persisted or unreadable sidecar state. If storage prevents creating it and rollback fails, only the current process retains the halt; operator repair/restoration is required before restart/advance.
- Subprocess resource limits contain this fixed regex workload; they are not an arbitrary-code sandbox.

## Pedro's first mission

Before running anything, write a prediction: why does the expensive rule pass functional tests yet fail the default performance gate? Run the demo, locate the exact rule hash/epoch for the timeout, compare `bad_canary.rollback` to the post-rollback HTTP result, and explain why API-down rollback proves HTTP-path independence but not host/storage resilience. Continue with [learning mission](learning-mission.md).

Cloudflare source: John Graham-Cumming, [Details of the outage on July 2, 2019](https://blog.cloudflare.com/details-of-the-cloudflare-outage-on-july-2-2019/). The question to its author remains a draft, not a sent message.
