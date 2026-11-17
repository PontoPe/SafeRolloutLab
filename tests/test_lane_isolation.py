import threading
from concurrent.futures import ThreadPoolExecutor
from saferollout.rules import RULES, ADVERSARIAL, version
from saferollout.router import Store, choose
from test_api import request


def test_candidate_has_no_access_to_stable_worker_capacity(tmp_path):
    from saferollout.api import create_server
    store = Store(tmp_path / 'route.json')
    route = store.initialize(RULES['stable'])
    route = store.update(route['epoch'], candidate=RULES['expensive'], percent=10)
    server = create_server(store.path, tmp_path / 'metrics.jsonl')
    assert server.stable_worker is not server.candidate_worker
    t = threading.Thread(target=server.serve_forever)
    t.start()
    url = f'http://127.0.0.1:{server.server_port}'
    candidate_ids = [str(i) for i in range(1000) if choose(route, str(i)) == version(RULES['expensive'])][:2]
    try:
        with ThreadPoolExecutor(max_workers=3) as executor:
            bad = [executor.submit(request, url + '/inspect', dict(text=ADVERSARIAL, request_id=rid))
                   for rid in candidate_ids]
            assert request(url + '/baseline', dict(text='hello', request_id='stable-probe'))[0] == 200
            assert all(f.result()[0] == 503 for f in bad)
    finally:
        server.shutdown()
        server.server_close()
        t.join(timeout=3)
