import json
import threading
from saferollout.rules import RULES, ADVERSARIAL, version
from saferollout.router import Store, choose
from saferollout.metrics import Journal
from test_api import request


def test_canary_only_defect_aborts_and_confirmed_rollback_serves_stable(tmp_path):
    from saferollout.api import create_server
    from saferollout.controller import Controller
    store = Store(tmp_path / 'route.json')
    store.initialize(RULES['stable'])
    c = Controller(store, minimum=10)
    route = c.begin(RULES['expensive'], profile='small')
    assert route['status'] == 'CANARY'
    server = create_server(store.path, tmp_path / 'metrics.jsonl')
    t = threading.Thread(target=server.serve_forever)
    t.start()
    url = f'http://127.0.0.1:{server.server_port}/inspect'
    rid = next(str(i) for i in range(1000) if choose(route, str(i)) == version(RULES['expensive']))
    try:
        status, result = request(url, dict(text=ADVERSARIAL, request_id=rid, expected_block=False))
        assert status == 503 and result['status'] == 'timeout'
        decision = c.observe(Journal(tmp_path / 'metrics.jsonl').read())
        assert decision['decision'] == 'REJECT'
        assert decision['rollback']['decision'] == 'ROLLED_BACK'
        assert request(url, dict(text=ADVERSARIAL, request_id='after', expected_block=False))[0] == 200
    finally:
        server.shutdown()
        server.server_close()
        t.join(timeout=3)
    c.begin(RULES['good'])
    # No HTTP server exists now. Dedicated control file still supports rollback.
    assert c.rollback('api_process_stopped')['decision'] == 'ROLLED_BACK'
