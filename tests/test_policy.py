from saferollout.rules import RULES
from saferollout.worker import Worker


def test_policy_is_entire_ascii_a_body_including_newline_edge():
    w = Worker()
    for name in ('stable', 'good', 'expensive'):
        assert w.evaluate(RULES[name]['pattern'], 'aaa\n')['matched'] is False
        assert w.evaluate(RULES[name]['pattern'], 'aaa')['matched'] is True
