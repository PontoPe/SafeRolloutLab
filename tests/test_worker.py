import os
import time
from concurrent.futures import ThreadPoolExecutor


def test_worker_matches_and_reaps_with_bounded_cpu():
    from saferollout.worker import Worker
    w = Worker(deadline=0.12)
    good = w.evaluate(r'a+$', 'aaaa')
    assert good['status'] == 'ok' and good['matched'] is True
    bad = w.evaluate(r'(a+)+$', 'a' * 30 + '!')
    assert bad['status'] == 'timeout'
    assert bad['elapsed_ms'] < 1500
    assert bad['cpu_ms'] >= 0
    for result in (good, bad):
        try:
            os.waitpid(result['pid'], os.WNOHANG)
        except ChildProcessError:
            pass
        else:
            raise AssertionError('worker not reaped')
