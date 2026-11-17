# Threat model

## Assets and boundary

Protect availability of the known-good inspection lane, correctness of block decisions, and honesty of rollout evidence. The candidate rule may accidentally introduce pathological backtracking or false positives. Request bodies may contain bounded worst-case strings. The operator, Python interpreter, project source, controller and same-user local filesystem are trusted. Only synthetic inputs are permitted.

## Controls

| Failure / abuse | Control and observable behavior |
|---|---|
| Regex backtracking | Only short-lived child executes `re`; CPU/AS/FD/process limits, supervisor wall timeout, SIGKILL and reap |
| Candidate capacity starvation | Separate stable/candidate slots and bounded queues; HTTP handler cap; controlled 503, no silent allow |
| Payload / queue / PID growth | Byte caps before spawning, one child per active lane, no child descendants, finite load |
| Functionally wrong rule | Positive and legitimate negative fixtures; false-positive candidate rejected |
| Weak performance suite | Explicit small-profile negative control, then canary timeout and abort |
| Missing/corrupt evidence | INCONCLUSIVE, no promotion; JSON/type/duplicates validation and epoch filtering |
| Stale/restarted controllers | Durable state, CAS epoch, terminal NOOP; persisted original rule |
| HTTP service outage | Dedicated local file control plane remains usable; route readback independently of HTTP |
| Control contention | Lock deadline and ROLLBACK_FAILED journal entry; no claim of restored service. A persisted HALTED latch, written before the route is touched, blocks begin/observe across restarts until an explicit verified rollback |
| Audit journal unavailable | Restoration still attempted; unaudited PASS is not applied; progression latched until a recorded operator recovery |
| Accidental credentials | No dotenv/credentials required; ignore `.env*`, safe example, fail-closed gitleaks hook and local CI scan |

## Residual risks / nonclaims

- Native resource limits are not container/cgroup CPU quotas, seccomp or protection from malicious Python/native code. No arbitrary code plugin execution is supported. Repeated authorized CLI use could exceed experiment budgets; this is not a multi-tenant service.
- A compromised local user can edit route/telemetry, bypass gitleaks or spoof `expected_block`. These annotations are trusted experiment ground truth, not user-controlled production authorization decisions. Route files are not signed and read-time schemas are not designed to tolerate malicious same-user edits.
- Both lanes share the frontend, interpreter, filesystem, CPU scheduler and host. Candidate child isolation does not promise availability through host/disk/frontend failure. Network is loopback only, but no authentication/TLS is present; do not expose it or use personal payloads.
- RLIMIT_NPROC applies per real UID and is Linux-specific; it prevents descendants in the normal unprivileged lab but is not a container PID quota. HTTP admission overload replies are not worker observations; client journals expose them, and incomplete load must not be mistaken for a complete stage.
- The observer is invoked by the finite experiment, not installed as a persistent scheduler. If the observer dies, routing remains at its persisted stage until observation or explicit rollback resumes. Rollback also requires an intact writable control file; lock/disk/state loss can prevent recovery.
- fsync/readback support observed local recovery, not distributed transactions, immunity to storage loss, or host-failure independence. Decision journals are not cryptographically immutable.
- Synthetic corpora and 100 candidate observations per stage are limited demonstrations, not security completeness, high-load capacity testing or production SLO evidence. Worker CPU includes startup; API elapsed time excludes network, which is separately captured in client logs.

No credentials, production systems, shared containers, AWS or external traffic were used to build or run the lab.
