# Learning mission for Pedro

Goal: understand SafeRollout Lab well enough to rebuild its reasoning on a whiteboard and defend every claim in [cv-bullets.md](cv-bullets.md) in an interview.

Rules for every exercise:

- **Predict first.** Write your prediction before running anything.
- **Change only this repo**, and use a new `.run/<name>` directory for each experiment (the demo refuses to overwrite one).
- **Finish with one observed fact and one remaining uncertainty.** If you cannot point to a file, a test or a log line, you have not finished.

Setup (once):

```sh
python3 -m venv .venv && . .venv/bin/activate
python -m pip install '.[test]'
python -m pytest -q          # expect: 23 passed
```

---

## Level 1 — Read the story (about 1 hour)

**1.1 The incident.** Read the [Cloudflare post-mortem](https://blog.cloudflare.com/details-of-the-cloudflare-outage-on-july-2-2019/), then [case-study.md](case-study.md) §1.

- Questions: Which three lessons did this lab take from the post-mortem? Which of them does the lab *not* address at all (think scale, global network, real traffic)?

**1.2 The demo.** Watch `docs/demo/saferollout-demo.gif` or replay `docs/demo/saferollout-demo.cast`.

- Questions: Name every decision word you see (`PASS`, `REJECTED`, `REJECT`, `INCONCLUSIVE`, `ROLLED_BACK`, `ROLLBACK_FAILED`, `HALTED`, `NOOP`). For each, say who produces it and what it means for the route.
- Where to look: `src/saferollout/controller.py`, `src/saferollout/metrics.py` (`assess`).

## Level 2 — Correct is not cheap (about 1 hour)

**2.1 Three rules.** Read `RULES`, `FIXTURES` and `ADVERSARIAL` in `src/saferollout/rules.py`.

- Predict: which rules pass `functional_gate`? Which pass `performance_gate`? Check with `tests/test_rules.py`.
- Question: why does `\A(a+)+\Z` explode on `'a' * 30 + '!'` but not on `'aaa'`? Explain backtracking in two sentences.

**2.2 Why a child process.** Read `src/saferollout/worker.py` and `worker_child.py`.

- Questions: Why can a thread timeout not stop a running Python `re` match? Which resource limits are set, and which one actually stops the expensive regex in practice (wall deadline or `RLIMIT_CPU`)? What does "reap" mean and what happens if you forget it?
- Exercise: run `python -m pytest -q tests/test_worker.py tests/test_bounds.py -v` and match each assertion to a limit.

**Interview check:** "Why didn't you just add a timeout to the regex call?"

## Level 3 — Staged rollout and telemetry (about 2 hours)

**3.1 Follow one hash.** Run `./scripts/demo.sh .run/mission-3 100`. Open `.run/mission-3/summary.json` and `.run/mission-3/metrics.jsonl`.

- Pick one response, find its rule hash and epoch in `metrics.jsonl`, then find the same hash in `route.json`.
- Read `choose()` in `src/saferollout/router.py`. Question: at 10%, why is the observed candidate share not exactly 10%? What makes the assignment reproducible?

**3.2 Do not promote on silence.** Read `assess()` in `src/saferollout/metrics.py`.

- Questions: List every path that returns `INCONCLUSIVE`. Why is a candidate timeout an immediate `REJECT` and not just a p95 effect? Why is an expected 403 not an error?
- Exercise (RED → GREEN): write a new test in `tests/test_metrics.py` with a telemetry row whose `elapsed_ms` is a string. Predict the decision, run it, and explain the result. If you find a gap, write the failing test first, then the smallest fix.

**3.3 Read the statistics.** From `metrics.jsonl`, recompute the nearest-rank p95 for one stage, grouped by epoch and version (a few lines of Python). Compare with `summary.json`.

- Questions: How many observations are above p95 when n=100? Why is there no p99? What is the `/baseline` cohort at the 100% stage and why is it not counted as exposure?

**Interview check:** "How do you know the canary was actually serving the new rule?"

## Level 4 — Control plane and honest failure (about 2 hours)

**4.1 Kill the data path, keep control.** In `src/saferollout/demo.py`, find `stop_api(api)` followed by `control('rollback')`.

- Questions: Why does rollback still work with the API process stopped? What does this prove, and what does it *not* prove (host loss, disk loss, the shared frontend)?
- Where to look: `Store` in `src/saferollout/router.py` (lock, epoch CAS, fsync, atomic rename, readback).

**4.2 Run it by hand.** Follow "Manual local session" and "Recover without HTTP" in [runbook.md](runbook.md): start the API, begin `good`, generate load, observe, then stop the API with Ctrl-C and roll back from another terminal.

- Question: why does the runbook say state readback alone is not a healthy-service claim?

**4.3 Honest recovery.** Read the lock-contention step in `demo.py` and `test_control_lock_has_deadline_and_records_failed_rollback` in `tests/test_hardening.py`.

- Questions: Distinguish `REJECT`, `ROLLED_BACK` and `ROLLBACK_FAILED`. What should an operator do after `ROLLBACK_FAILED`? Why must they never delete a live lock file?

**Interview check:** "Your rollback failed. What does the system do, and what does it refuse to say?"

## Level 5 — The defect you must be able to explain (about 2 hours)

Read [case-study.md](case-study.md) §4 first.

**5.1 Reproduce the bug.** Open `docs/evidence/halt-01-red.txt`. Then, on a throwaway branch, comment out the two `if self._halted(): ...` checks in `controller.py` and run:

```sh
python -m pytest -q tests/test_controller.py -k halts_across_restart
```

- Predict the failure before running. Restore the file with `git checkout -- src/saferollout/controller.py` afterwards and rerun the full suite.

**5.2 Understand the fix.** Read `_halted`, `_latch`, `_record` and `rollback` in `controller.py`.

- Questions: Why is the latch written *before* the route is touched? When exactly is it cleared? Why does an unaudited `PASS` not advance the stage? What happens when the sidecar file cannot be written, and what does a new process do if the sidecar is unreadable?
- Read the three regression tests (`test_failed_final_stage_rollback_halts_across_restart_until_recovery`, `test_audit_failure_still_restores_and_requires_explicit_recovery`, `test_unwritable_halt_latch_still_restores_and_halts_in_process`) and describe each in one sentence.

**5.3 Find the remaining hole.** Questions: Why must controller commands still be serialized? Describe a sequence with two overlapping controllers where the halt check and the route update interleave badly. What would a fix look like? (Do not claim it is fixed; it is listed as a next step.)

**Interview check:** "Tell me about a bug you found and how you made sure it stays fixed."

## Level 6 — CI, secrets and limits (about 1 hour)

**6.1 CI.** Read `.github/workflows/ci.yml`.

- Questions: Why pin actions by commit SHA instead of a tag? What does `permissions: contents: read` prevent? Why `persist-credentials: false`? Why verify the gitleaks download with SHA-256? Why scan the full Git history and not only the working tree?
- Exercise: open the latest run on the [Actions page](https://github.com/PontoPe/SafeRolloutLab/actions/workflows/ci.yml) and confirm its commit SHA matches `main`.

**6.2 Limits out loud.** Without notes, explain each limit in the README "Limits" section in one sentence: no Docker, no HA, no watchdog, not production-ready, single operator, storage-dependent halt, regex-only resource limits.

- Question: an interviewer says "so this is basically a WAF with canary deploys". Correct them precisely.

## Level 7 — Extend it (optional, open-ended)

Pick one item from [case-study.md](case-study.md) §6, write the prediction and a failing test first, and keep raw evidence. Good first choices: run the same experiment with the default 1,000 observations and accept an `INCONCLUSIVE` result if the load budget is too small; or prototype making the halt check and route update one locked operation.

---

## Done when

You can, without notes: draw the architecture diagram from the README, walk through one request from load generator to metric row, explain every decision word, reproduce and explain the halt-latch defect, and list the limits. Then the bullets in [cv-bullets.md](cv-bullets.md) are yours to use.

## Question drafted for the article author (not sent)

After the 2019 incident, what operational evidence proved that the emergency rollback path remained usable while the rule-evaluation data plane was saturated, and how were per-rule cost tests and staged-rollout stop conditions validated against missing telemetry rather than only explicit error signals?
