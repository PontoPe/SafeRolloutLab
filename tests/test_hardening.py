import fcntl
import math
import time
import pytest
from saferollout.metrics import assess
from saferollout.router import Store
from saferollout.rules import RULES
from test_metrics import rows


def test_malformed_telemetry_is_inconclusive_not_a_crash():
    for change in ({'elapsed_ms': 'fast'}, {'elapsed_ms': float('nan')}, {'elapsed_ms': -1},
                   {'expected_block': 'false'}, {'status': None}, {'version': 'unknown'}):
        data = rows('s', 10) + rows('c', 10)
        data[-1].update(change)
        assert assess(data, 's', 'c', minimum=10)['decision'] == 'INCONCLUSIVE'


def test_control_lock_has_deadline_and_records_failed_rollback(tmp_path):
    from saferollout.controller import Controller
    store = Store(tmp_path / 'route.json')
    store.initialize(RULES['stable'])
    c = Controller(store, minimum=10)
    c.begin(RULES['good'])
    with open(str(store.path) + '.lock', 'a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        started = time.monotonic()
        assert c.rollback('lock_unavailable')['decision'] == 'ROLLBACK_FAILED'
        assert time.monotonic() - started < 2
    assert store.read()['status'] == 'CANARY'
    assert c.rollback('retry_after_unlock')['decision'] == 'ROLLED_BACK'
