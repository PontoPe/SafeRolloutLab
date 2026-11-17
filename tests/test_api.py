import json
import threading
import urllib.error
import urllib.request

from saferollout.router import Store
from saferollout.rules import RULES, version


def request(url, body):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={'Content-Type': 'application/json'})
    try:
        response = urllib.request.urlopen(req, timeout=3)
    except urllib.error.HTTPError as exc:
        response = exc
    with response:
        return response.status, json.load(response)


def test_live_http_versions_blocking_payload_and_metrics(tmp_path):
    from saferollout.api import create_server
    from saferollout.metrics import Journal
    store = Store(tmp_path / 'route.json')
    store.initialize(RULES['stable'])
    server = create_server(store.path, tmp_path / 'metrics.jsonl', port=0)
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    url = f'http://127.0.0.1:{server.server_port}/inspect'
    try:
        status, row = request(url, {'text': 'aaa', 'request_id': 'one', 'expected_block': True})
        assert status == 403 and row['matched'] is True
        assert row['version'] == version(RULES['stable'])
        status, row = request(url, {'text': 'hello', 'request_id': 'two', 'expected_block': False})
        assert status == 200
        assert request(url, {'text': 'x' * 4097, 'request_id': 'big'})[0] == 413
        assert request(url, {'text': 'ok', 'request_id': []})[0] == 400
        metrics = Journal(tmp_path / 'metrics.jsonl').read()
        assert len(metrics) == 2 and metrics[0]['cpu_ms'] > 0
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
