import pytest
from saferollout.rules import RULES
from saferollout.router import Store
from saferollout.metrics import Journal


def test_noop_rule_cannot_create_fake_two_version_evidence(tmp_path):
    from saferollout.controller import Controller
    store = Store(tmp_path / 'route.json')
    store.initialize(RULES['stable'])
    with pytest.raises(ValueError, match='same version'):
        Controller(store).begin(RULES['stable'])


def test_load_generator_cannot_target_external_hosts(tmp_path):
    from saferollout.loadgen import run
    with pytest.raises(ValueError, match='loopback'):
        run('https://example.com', tmp_path / 'missing.json', tmp_path / 'client.jsonl')


def test_journal_rejects_oversized_input_before_append(tmp_path):
    journal = Journal(tmp_path / 'test.jsonl')
    with pytest.raises(OSError):
        journal.append({'untrusted': 'x' * (16 * 1024 * 1024)})
    assert not journal.path.exists()
