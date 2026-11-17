"""Synthetic policy: block bodies consisting entirely of letter a."""
import hashlib
import json
from .worker import Worker

RULES = {
    'stable': {'name': 'stable', 'pattern': '\\Aa+\\Z'},
    'good': {'name': 'good', 'pattern': '\\Aaa*\\Z'},
    'expensive': {'name': 'expensive', 'pattern': '\\A(a+)+\\Z'},
    'false-positive': {'name': 'false-positive', 'pattern': 'a'},
}
FIXTURES = [('aaa', True), ('a', True), ('hello', False), ('account', False), ('aaa!', False)]
ADVERSARIAL = 'a' * 30 + '!'


def version(rule):
    return hashlib.sha256(json.dumps(rule, sort_keys=True).encode()).hexdigest()


def validate(rule):
    if not isinstance(rule, dict) or set(rule) != {'name', 'pattern'}:
        return False
    if not all(isinstance(v, str) and v for v in rule.values()):
        return False
    if len(rule['name']) > 64 or len(rule['pattern']) > 256:
        return False
    return Worker().evaluate(rule['pattern'], '')['status'] == 'ok'


def functional_gate(rule, worker):
    if not validate(rule):
        return {'decision': 'REJECT', 'reason': 'schema_or_regex'}
    rows = [dict(text=text, expected=expected, **worker.evaluate(rule['pattern'], text))
            for text, expected in FIXTURES]
    return {'decision': 'PASS' if all(r['status'] == 'ok' and r['matched'] == r['expected'] for r in rows) else 'REJECT',
            'reason': 'functional', 'observations': rows, 'version': version(rule)}


def performance_gate(rule, worker, profile='adversarial'):
    if profile not in ('small', 'adversarial'):
        raise ValueError('unknown profile')
    row = worker.evaluate(rule['pattern'], 'aaaa!' if profile == 'small' else ADVERSARIAL)
    row['profile'] = profile
    return {'decision': 'PASS' if row['status'] == 'ok' and row['elapsed_ms'] <= 100 else 'REJECT',
            'reason': 'bounded_adversarial_profile', 'observations': [row], 'version': version(rule)}
