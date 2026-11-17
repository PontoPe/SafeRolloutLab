# Recorded demo — real commands, real HTTP

Download [demo.cast](publication/demo.cast?raw=true) and replay with an asciicast-v2-compatible player, for example `asciinema play demo.cast` (optional viewer, not a project dependency). GitHub does not play casts inline. The [plain transcript](publication/transcript.txt) is extracted from the same recording. No terminal frames, test results or benchmark values were fabricated.

The recording runs:

1. `python3 -m pytest -q`: 23 tests, including the small real-process integration experiment.
2. `./scripts/demo.sh docs/demo/publication/evidence 100`: full finite loopback HTTP experiment, separate load generator and fresh controller process per decision.
3. `python3 scripts/record-demo.py --report docs/demo/publication/evidence/summary.json`: reads the actual summary and verifies runtime source hashes against this checkout.

Observed: 1,510 server observations, 1 intentional bounded regex timeout, good rule PASS at 10/50/100%, false-positive/default expensive preflight REJECTED, blind-profile canary REJECT followed by verified rollback, missing/insufficient telemetry INCONCLUSIVE, API-stopped rollback ROLLED_BACK, deliberate lock contention ROLLBACK_FAILED, then explicit recovery ROLLED_BACK. Post-rollback HTTP returned 200; both API processes were reaped.

Raw [summary](publication/evidence/summary.json), [commands](publication/evidence/commands.jsonl), [server metrics](publication/evidence/metrics.jsonl) and client JSONL remain separate from the earlier `native-mvp-03` run. Do not merge runs or reuse timing values as production SLOs. The default policy is 1,000 observations/version/stage; this recorded shared-host demonstration explicitly uses 100. Statistical and host/storage limitations remain those in the [case](../technical-case.md) and [historical report](../delivery-report.md).

Record a new run without overwriting this evidence:

```sh
python3 scripts/record-demo.py
```

The stdlib recorder uses a PTY and monotonic timestamps, saves real output as asciicast v2, and propagates command failure. Its default output is a fresh ignored `.run/recording-<UTC>/` directory. The recording predates its publication commit: the summary uses exact runtime source SHA-256 values; none of the nine runtime modules changed during publication.
