import json
import pytest


def test_route_persistence_determinism_and_compare_swap(tmp_path):
    from saferollout.router import Store, Conflict, choose
    from saferollout.rules import RULES, version
    store = Store(tmp_path / 'route.json')
    initial = store.initialize(RULES['stable'])
    assert Store(store.path).read() == initial
    route = store.update(initial['epoch'], candidate=RULES['good'], percent=10)
    assert sum(choose(route, str(i)) == version(RULES['good']) for i in range(1000)) in range(60, 140)
    assert [choose(route, str(i)) for i in range(100)] == [choose(store.read(), str(i)) for i in range(100)]
    with pytest.raises(Conflict):
        store.update(initial['epoch'], percent=100)
    with pytest.raises(ValueError):
        store.update(route['epoch'], percent=101)
    assert store.read() == route
