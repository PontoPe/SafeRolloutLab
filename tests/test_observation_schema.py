from saferollout.router import Store
from saferollout.rules import RULES


def test_valid_json_nonobject_telemetry_cannot_crash_controller(tmp_path):
    from saferollout.controller import Controller
    store = Store(tmp_path / 'route.json')
    store.initialize(RULES['stable'])
    c = Controller(store, minimum=10)
    c.begin(RULES['good'])
    assert c.observe([None, ['not', 'a', 'row']])['decision'] == 'INCONCLUSIVE'
    assert store.read()['percent'] == 10
