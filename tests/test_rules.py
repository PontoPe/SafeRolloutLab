def test_functional_equivalence_is_not_performance_safety():
    from saferollout.rules import RULES, functional_gate, performance_gate, validate
    from saferollout.worker import Worker
    w = Worker()
    assert functional_gate(RULES['good'], w)['decision'] == 'PASS'
    assert functional_gate(RULES['expensive'], w)['decision'] == 'PASS'
    assert functional_gate(RULES['false-positive'], w)['decision'] == 'REJECT'
    assert performance_gate(RULES['good'], w)['decision'] == 'PASS'
    assert performance_gate(RULES['expensive'], w)['decision'] == 'REJECT'
    for invalid in ({}, {'name': 'oops', 'pattern': '('}, {'name': 'bad', 'pattern': 'x' * 257}):
        assert validate(invalid) is False
