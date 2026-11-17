# Learning missions for Pedro

Each mission changes only this project, starts with a prediction, then a failing test or bounded experiment. Preserve raw evidence and finish with one observed fact and one remaining uncertainty.

1. **Correct does not mean cheap.** Predict why `expensive` passes the small corpus. Inspect functional observations, then run the default bounded adversarial gate. Explain why a thread timeout would not safely cancel Python `re`.
2. **Follow one hash.** Read an HTTP response, find its exact rule hash/epoch in metrics, then trace the persisted route. Find how request ID hashing picks the canary; distinguish deterministic assignment from an exact observed 10% count.
3. **Prove a negative.** Change only a local synthetic legitimate fixture and write a failing test that catches the false-positive rule. Keep intentional 403 blocks separate from availability errors.
4. **A blind preflight.** Inspect the explicitly weak `small` profile experiment. Compare the same bounded adversarial body on stable and candidate. Identify child CPU, wall deadline, actual HTTP error and confirmed route recovery; do not invent a p95 for one timeout.
5. **Kill the data path, keep control.** Reproduce the API-stopped rollback using the demo. Explain why that proves independence from HTTP but not independence from the host/filesystem. Verify stable routing after restart.
6. **Do not promote on silence.** Write a RED test for a new malformed telemetry value, implement the smallest safe INCONCLUSIVE response, then rerun all tests. Try the default 1,000 policy only within the finite load budget and accept an inconclusive result.
7. **Honest recovery.** Read the lock-contention negative control. Distinguish `REJECT`, `ROLLED_BACK` and `ROLLBACK_FAILED`; formulate an operator action that does not delete a live lock or claim unobserved recovery.
8. **Read the statistics.** Recompute nearest-rank p95 from raw metrics grouped by epoch/version. Count tail observations at n=100, explain why there is no p99, and identify the `/baseline` control cohort at the 100% stage.

## Question drafted for the article author (not sent)

After the 2019 incident, what operational evidence proved that the emergency rollback path remained usable while the rule-evaluation data plane was saturated, and how were per-rule cost tests and staged-rollout stop conditions validated against missing telemetry rather than only explicit error signals?
