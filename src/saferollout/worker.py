"""Bounded, killable regex supervisor. Linux wait4 measures each child's CPU."""
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time


class MeasuredProcess(subprocess.Popen):
    cpu_ms = 0.0

    def _try_wait(self, wait_flags):
        pid, status, usage = os.wait4(self.pid, wait_flags)
        if pid:
            self.cpu_ms = (usage.ru_utime + usage.ru_stime) * 1000
        return pid, status


class Worker:
    def __init__(self, deadline=0.12, concurrency=2, queue=2):
        if not 0.03 <= deadline <= 0.5 or not 1 <= concurrency <= 4 or not 0 <= queue <= 8:
            raise ValueError('unsafe worker bounds')
        self.deadline = deadline
        self.slots = threading.BoundedSemaphore(concurrency + queue)
        self.running = threading.BoundedSemaphore(concurrency)
        self.lock = threading.Lock()
        self.active = 0

    def evaluate(self, pattern, text):
        if not isinstance(text, str) or len(text.encode()) > 4096 or len(pattern) > 256:
            return {'status': 'payload_too_large'}
        if not self.slots.acquire(blocking=False):
            return {'status': 'overloaded'}
        start = time.monotonic()
        acquired = self.running.acquire(timeout=self.deadline)
        try:
            if not acquired:
                return {'status': 'queue_timeout', 'elapsed_ms': (time.monotonic() - start) * 1000}
            with self.lock:
                self.active += 1
            try:
                return self._run(pattern, text, start, (time.monotonic() - start) * 1000)
            finally:
                with self.lock:
                    self.active -= 1
        finally:
            if acquired:
                self.running.release()
            self.slots.release()

    def _run(self, pattern, text, start, queue_ms):
        p = MeasuredProcess([sys.executable, str(Path(__file__).with_name('worker_child.py'))],
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        status = 'ok'
        try:
            out, _ = p.communicate(json.dumps([pattern, text]).encode(), timeout=self.deadline)
        except subprocess.TimeoutExpired:
            p.kill()
            out, _ = p.communicate()
            status = 'timeout'
        if p.returncode and status == 'ok':
            status = 'worker_error'
        return {'status': status, 'matched': json.loads(out)['matched'] if status == 'ok' else False,
                'pid': p.pid, 'elapsed_ms': (time.monotonic() - start) * 1000,
                'cpu_ms': p.cpu_ms, 'queue_ms': queue_ms}
