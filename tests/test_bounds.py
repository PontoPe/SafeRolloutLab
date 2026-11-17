import time
from concurrent.futures import ThreadPoolExecutor


def test_worker_payload_cpu_and_queue_bounds():
    from saferollout.worker import Worker
    w = Worker(deadline=0.15, concurrency=1, queue=0)
    assert w.evaluate('a', 'x' * 4097)['status'] == 'payload_too_large'
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(w.evaluate, r'(a+)+$', 'a' * 30 + '!')
        limit = time.monotonic() + 1
        while w.active == 0 and time.monotonic() < limit:
            time.sleep(0.001)
        second = w.evaluate('a', 'a')
        assert second['status'] == 'overloaded'
        result = first.result()
        assert result['cpu_ms'] > 0
    assert w.active == 0
