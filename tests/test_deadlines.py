import time
from concurrent.futures import ThreadPoolExecutor
from saferollout.worker import Worker
from saferollout.rules import RULES
from saferollout.router import Store


def test_control_characters_and_actual_queue_wait_are_measured():
    w = Worker(deadline=.2, concurrency=1, queue=1)
    assert w.evaluate('a', '\x00' * 4096)['status'] == 'ok'
    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(w.evaluate, '(a+)+$', 'a' * 30 + '!')
        while w.active == 0:
            time.sleep(.001)
        time.sleep(.03)
        second = executor.submit(w.evaluate, 'a', 'a').result()
        first.result()
    assert second['status'] == 'ok'
    assert second['queue_ms'] > 50


def test_expired_stage_never_promotes_old_samples(tmp_path):
    from saferollout.controller import Controller
    store = Store(tmp_path / 'route.json')
    store.initialize(RULES['stable'])
    c = Controller(store, minimum=10)
    route = c.begin(RULES['good'])
    store.update(route['epoch'], started=time.time() - 121)
    result = c.observe([])
    assert result['decision'] == 'INCONCLUSIVE'
    assert result['reason'] == 'stage_deadline'
    assert result['rollback']['decision'] == 'ROLLED_BACK'
