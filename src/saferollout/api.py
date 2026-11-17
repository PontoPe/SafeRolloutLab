"""Loopback-only lab HTTP server. Not an Internet-facing production service."""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import socket
import threading
import time

from .metrics import Journal
from .router import Store, choose
from .rules import version
from .worker import Worker


class BoundedServer(ThreadingHTTPServer):
    daemon_threads = False
    block_on_close = True
    request_queue_size = 8

    def __init__(self, *args, **kwargs):
        self.http_slots = threading.BoundedSemaphore(4)
        super().__init__(*args, **kwargs)

    def process_request(self, request, address):
        request.settimeout(1)
        if not self.http_slots.acquire(blocking=False):
            row = {'status': 'http_overloaded', 'version': version(self.store.read()['stable'])}
            body = json.dumps(row).encode()
            try:
                request.sendall(b'HTTP/1.0 503 Service Unavailable\r\nContent-Type: application/json\r\nContent-Length: ' + str(len(body)).encode() + b'\r\n\r\n' + body)
            except OSError:
                pass
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, address)
        except BaseException:
            self.http_slots.release()
            raise

    def process_request_thread(self, request, address):
        try:
            super().process_request_thread(request, address)
        finally:
            self.http_slots.release()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def send_json(self, code, body):
        encoded = json.dumps(body, sort_keys=True).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(encoded)))
        self.end_headers()
        try:
            self.wfile.write(encoded)
        except OSError:
            pass

    def do_GET(self):
        route = self.server.store.read()
        self.send_json(200 if self.path == '/health' else 404,
                       {'version': version(route['stable']), 'epoch': route['epoch'], 'status': 'ready'})

    def do_POST(self):
        route = self.server.store.read()
        base = {'version': version(route['stable']), 'epoch': route['epoch']}
        if self.path not in ('/inspect', '/baseline'):
            return self.send_json(404, {**base, 'status': 'not_found'})
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if self.headers.get('Transfer-Encoding') or not 0 < length <= 8192:
                return self.send_json(413, {**base, 'status': 'body_limit'})
            data = json.loads(self.rfile.read(length))
            if not isinstance(data, dict):
                raise ValueError('body must be object')
            text, rid = data['text'], data['request_id']
            expected = data.get('expected_block', False)
            if not isinstance(text, str) or not isinstance(rid, str) or not 1 <= len(rid.encode()) <= 128 or not isinstance(expected, bool):
                raise ValueError('invalid schema')
            if len(text.encode()) > 4096:
                return self.send_json(413, {**base, 'status': 'payload_too_large'})
        except (ValueError, KeyError, OSError, TypeError):
            return self.send_json(400, {**base, 'status': 'invalid_request'})
        chosen = version(route['stable']) if self.path == '/baseline' else choose(route, rid)
        rule = route['candidate'] if route['candidate'] and chosen == version(route['candidate']) else route['stable']
        started = time.monotonic()
        try:
            worker = self.server.candidate_worker if rule == route['candidate'] else self.server.stable_worker
            result = worker.evaluate(rule['pattern'], text)
        except OSError:
            result = {'status': 'worker_error'}
        row = dict(version=chosen, epoch=route['epoch'], request_id=rid,
                   expected_block=expected, matched=result.get('matched', False),
                   status=result['status'], elapsed_ms=(time.monotonic() - started) * 1000,
                   worker_ms=result.get('elapsed_ms'), cpu_ms=result.get('cpu_ms'),
                   queue_ms=result.get('queue_ms'), cohort='control' if self.path == '/baseline' else 'routed',
                   candidate=bool(rule == route['candidate']), time=time.time())
        code = 200 if row['status'] == 'ok' else 503
        if code == 200 and row['matched']:
            code = 403
        try:
            self.server.journal.append(row)
        except OSError:
            row['status'] = 'telemetry_unavailable'
            code = 503
        self.send_json(code, row)


def create_server(state, metrics, port=0):
    server = BoundedServer(('127.0.0.1', port), Handler)
    server.store = Store(state)
    server.journal = Journal(metrics)
    server.stable_worker = Worker(concurrency=1, queue=1)
    server.candidate_worker = Worker(concurrency=1, queue=1)
    return server


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--state', required=True)
    parser.add_argument('--metrics', required=True)
    parser.add_argument('--ready', required=True)
    parser.add_argument('--port', type=int, default=0)
    args = parser.parse_args()
    server = create_server(args.state, args.metrics, args.port)
    Path(args.ready).write_text(json.dumps({'port': server.server_port, 'pid': __import__('os').getpid()}))
    try:
        server.serve_forever(poll_interval=.1)
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
