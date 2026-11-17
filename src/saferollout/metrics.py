"""Version-scoped nearest-rank p95; intentionally no p99 on small lab samples."""
import json
import math
from pathlib import Path
import threading

MAX_TELEMETRY = 16 * 1024 * 1024


class Journal:
    def __init__(self, path):
        self.path = Path(path)
        self.lock = threading.Lock()

    def append(self, row):
        encoded = json.dumps(row, sort_keys=True) + '\n'
        with self.lock:
            if (self.path.stat().st_size if self.path.exists() else 0) + len(encoded.encode()) > MAX_TELEMETRY:
                raise OSError('telemetry budget exhausted')
            with self.path.open('a') as f:
                f.write(encoded)

    def read(self):
        if not self.path.exists() or self.path.stat().st_size > MAX_TELEMETRY:
            return []
        try:
            return [json.loads(line) for line in self.path.read_text().splitlines()]
        except (OSError, ValueError):
            return []


def assess(rows, stable, candidate, minimum=1000):
    required = {'version', 'request_id', 'elapsed_ms', 'status', 'expected_block', 'matched'}
    if not rows or any(not isinstance(r, dict) or not required <= r.keys() for r in rows):
        return {'decision': 'INCONCLUSIVE', 'reason': 'missing_telemetry'}
    for r in rows:
        if (r['version'] not in (stable, candidate) or
                not isinstance(r['request_id'], str) or not r['request_id'] or
                type(r['elapsed_ms']) not in (int, float) or
                not math.isfinite(r['elapsed_ms']) or r['elapsed_ms'] < 0 or
                type(r['expected_block']) is not bool or type(r['matched']) is not bool or
                r['status'] not in ('ok', 'timeout', 'worker_error', 'queue_timeout', 'overloaded')):
            return {'decision': 'INCONCLUSIVE', 'reason': 'invalid_telemetry'}
    if len({r['request_id'] for r in rows}) != len(rows):
        return {'decision': 'INCONCLUSIVE', 'reason': 'duplicate_telemetry'}
    groups = {v: [r for r in rows if r['version'] == v] for v in (stable, candidate)}
    counts = {v: len(g) for v, g in groups.items()}
    if any(r['status'] != 'ok' or r['elapsed_ms'] > 250 or r['matched'] != r['expected_block']
           for r in groups[candidate]):
        return {'decision': 'REJECT', 'reason': 'candidate_failure_or_absolute_budget', 'counts': counts}
    if any(n < minimum for n in counts.values()):
        return {'decision': 'INCONCLUSIVE', 'reason': 'insufficient_sample', 'counts': counts, 'minimum': minimum}
    p95 = {v: sorted(r['elapsed_ms'] for r in g)[math.ceil(len(g) * .95) - 1] for v, g in groups.items()}
    errors = {v: sum(r['status'] != 'ok' for r in g) / len(g) for v, g in groups.items()}
    regression = p95[candidate] > max(50, p95[stable] * 2) or errors[candidate] > errors[stable] + .01
    return {'decision': 'REJECT' if regression else 'PASS', 'reason': 'relative_budget',
            'counts': counts, 'p95_ms': p95, 'error_rates': errors, 'minimum': minimum}
