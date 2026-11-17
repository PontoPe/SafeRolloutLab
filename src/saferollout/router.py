"""Dedicated local control plane: atomic durable CAS plus readback, no API dependency."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time

from .rules import version


class Conflict(RuntimeError):
    pass


def choose(route, request_id):
    bucket = int.from_bytes(hashlib.sha256(request_id.encode()).digest()[:8], 'big') % 100
    rule = route['candidate'] if route['candidate'] and bucket < route['percent'] else route['stable']
    return version(rule)


class Store:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def read(self):
        return json.loads(self.path.read_text())

    def initialize(self, stable):
        with self._lock():
            if self.path.exists():
                return self.read()
            row = dict(epoch=0, stable=stable, candidate=None, percent=0,
                       status='IDLE', stage=0, original=stable)
            return self._write(row)

    def _lock(self):
        class Lock:
            def __enter__(inner):
                inner.file = open(str(self.path) + '.lock', 'a')
                deadline = time.monotonic() + 0.5
                while True:
                    try:
                        fcntl.flock(inner.file, fcntl.LOCK_EX | fcntl.LOCK_NB)
                        break
                    except BlockingIOError:
                        if time.monotonic() >= deadline:
                            inner.file.close()
                            raise TimeoutError('control lock deadline')
                        time.sleep(.005)
            def __exit__(inner, *args):
                inner.file.close()
        return Lock()

    def update(self, expected_epoch, **changes):
        with self._lock():
            current = self.read()
            if current['epoch'] != expected_epoch:
                raise Conflict('route epoch changed')
            row = {**current, **changes, 'epoch': expected_epoch + 1}
            if not isinstance(row['percent'], int) or row['percent'] not in range(101):
                raise ValueError('invalid percentage')
            return self._write(row)

    def _write(self, row):
        fd, name = tempfile.mkstemp(prefix='.route-', dir=self.path.parent)
        try:
            with os.fdopen(fd, 'w') as f:
                json.dump(row, f, sort_keys=True)
                f.flush()
                os.fsync(f.fileno())
            os.replace(name, self.path)
            directory = os.open(self.path.parent, os.O_DIRECTORY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
            observed = self.read()
            if observed != row:
                raise Conflict('readback mismatch')
            return observed
        finally:
            if os.path.exists(name):
                os.unlink(name)
