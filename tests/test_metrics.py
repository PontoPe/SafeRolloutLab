def rows(ver, count, latency=20, status='ok'):
    return [dict(version=ver, epoch=1, request_id=f'{ver}-{i}', elapsed_ms=latency,
                 status=status, expected_block=False, matched=False) for i in range(count)]


def test_metrics_gate_refuses_missing_small_or_duplicate_and_aborts_timeouts():
    from saferollout.metrics import assess
    assert assess([], 's', 'c', minimum=1000)['decision'] == 'INCONCLUSIVE'
    assert assess(rows('s', 20) + rows('c', 20), 's', 'c', minimum=1000)['decision'] == 'INCONCLUSIVE'
    evidence = rows('s', 1000) + rows('c', 1000)
    assert assess(evidence, 's', 'c')['decision'] == 'PASS'
    assert assess(evidence + [evidence[-1]], 's', 'c')['decision'] == 'INCONCLUSIVE'
    assert assess(rows('s', 1000) + rows('c', 1000, latency=90), 's', 'c')['decision'] == 'REJECT'
    assert assess(rows('c', 1, status='timeout'), 's', 'c')['decision'] == 'REJECT'
    assert assess([{'version': 'c'}], 's', 'c')['decision'] == 'INCONCLUSIVE'
