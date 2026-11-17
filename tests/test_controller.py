import fcntl
import time

from saferollout.rules import RULES, version
from saferollout.router import Store
from test_metrics import rows


def test_controller_recovers_stages_and_promotes_once(tmp_path):
    from saferollout.controller import Controller
    store = Store(tmp_path / 'route.json')
    store.initialize(RULES['stable'])
    c = Controller(store, minimum=10)
    assert c.begin(RULES['false-positive'])['status'] == 'REJECTED'
    assert c.begin(RULES['expensive'])['status'] == 'REJECTED'
    active = c.begin(RULES['good'])
    assert active['percent'] == 10
    s, v = version(RULES['stable']), version(RULES['good'])
    assert c.observe([])['decision'] == 'INCONCLUSIVE'
    assert store.read()['percent'] == 10
    for stage in (50, 100, 100):
        c = Controller(Store(store.path), minimum=10)
        route = store.read()
        observations = [{**r, 'epoch': route['epoch']} for r in rows(s, 10) + rows(v, 10)]
        c.observe(observations)
        assert store.read()['percent'] == stage
    promoted = store.read()
    assert promoted['status'] == 'PROMOTED' and version(promoted['stable']) == v
    assert c.observe(observations)['decision'] == 'NOOP'
    assert store.read() == promoted


def test_controller_rollback_independent_and_failure_is_honest(tmp_path):
    from saferollout.controller import Controller
    store = Store(tmp_path / 'route.json')
    store.initialize(RULES['stable'])
    c = Controller(store, minimum=10)
    c.begin(RULES['good'])
    assert c.rollback('canary_api_unavailable')['decision'] == 'ROLLED_BACK'
    assert version(store.read()['stable']) == version(RULES['stable'])
    assert store.read()['percent'] == 0
    c.begin(RULES['good'])
    store.path.unlink()
    failure = c.rollback('control_state_unavailable')
    assert failure['decision'] == 'ROLLBACK_FAILED'
    assert c.audit.read()[-1]['decision'] == 'ROLLBACK_FAILED'


def test_failed_final_stage_rollback_halts_across_restart_until_recovery(tmp_path):
    from saferollout.controller import Controller
    store = Store(tmp_path / 'route.json')
    store.initialize(RULES['stable'])
    c = Controller(store, minimum=10)
    active = c.begin(RULES['good'])
    active = store.update(active['epoch'], stage=2, percent=100)
    passing = [{**r, 'epoch': active['epoch']} for r in
               rows(version(RULES['stable']), 10) + rows(version(RULES['good']), 10)]
    with open(str(store.path) + '.lock', 'a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        started = time.monotonic()
        assert c.rollback('operator_requested')['decision'] == 'ROLLBACK_FAILED'
        assert time.monotonic() - started < 1.5
    c = Controller(Store(store.path), minimum=10)
    assert c.observe(passing)['decision'] == 'HALTED'
    assert c.begin(RULES['good'])['decision'] == 'HALTED'
    assert store.read() == active
    assert c.rollback('operator_requested')['decision'] == 'ROLLED_BACK'
    assert c.begin(RULES['good'])['status'] == 'CANARY'


def test_audit_failure_still_restores_and_requires_explicit_recovery(tmp_path):
    from saferollout.controller import Controller
    store = Store(tmp_path / 'route.json')
    store.initialize(RULES['stable'])
    c = Controller(store, minimum=10)
    active = c.begin(RULES['good'])
    active = store.update(active['epoch'], stage=2, percent=100)
    bad = [{**r, 'epoch': active['epoch'], 'status': 'timeout'}
           for r in rows(version(RULES['good']), 10)]
    c.audit.path.mkdir()
    result = c.observe(bad)
    assert result['decision'] == 'REJECT'
    assert 'audit_error' in result
    assert result['rollback']['decision'] == 'ROLLED_BACK'
    assert store.read()['percent'] == 0
    c = Controller(Store(store.path), minimum=10)
    assert c.begin(RULES['good'])['decision'] == 'HALTED'
    assert c.observe([])['decision'] == 'HALTED'
    assert 'audit_error' in c.rollback('operator_requested')
    assert c.begin(RULES['good'])['decision'] == 'HALTED'
    c.audit.path.rmdir()
    assert c.rollback('operator_requested')['decision'] == 'ROLLED_BACK'
    assert c.begin(RULES['good'])['status'] == 'CANARY'


def test_unwritable_halt_latch_still_restores_and_halts_in_process(tmp_path):
    from saferollout.controller import Controller
    store = Store(tmp_path / 'route.json')
    store.initialize(RULES['stable'])
    c = Controller(store, minimum=10)
    active = c.begin(RULES['good'])
    c.safety.path.mkdir()  # os.replace onto a directory fails: latch cannot persist
    result = c.rollback('operator_requested')
    assert result['decision'] == 'ROLLED_BACK'
    assert 'latch_error' in result
    assert store.read()['percent'] == 0 and store.read()['epoch'] == active['epoch'] + 1
    assert c.begin(RULES['good'])['decision'] == 'HALTED'
    assert c.observe([])['decision'] == 'HALTED'
    # A fresh process cannot read the latch either and must fail closed.
    assert Controller(Store(store.path), minimum=10).begin(RULES['good'])['decision'] == 'HALTED'
