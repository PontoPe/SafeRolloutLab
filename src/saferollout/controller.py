"""Persisted rollout state machine, operated independently from the HTTP process."""
import argparse
import json
import time

from .metrics import Journal, assess
from .router import Store
from .rules import RULES, functional_gate, performance_gate, version
from .worker import Worker

STAGES = (10, 50, 100)


class Controller:
    def __init__(self, store, minimum=1000):
        if not 10 <= minimum <= 10000:
            raise ValueError('minimum out of lab bounds')
        self.store = store
        self.minimum = minimum
        self.audit = Journal(str(store.path) + '.decisions.jsonl')
        self.safety = Store(str(store.path) + '.safety.json')
        # In-process latch: still halts this controller if the sidecar itself
        # cannot be written. Across restarts only the persisted sidecar counts.
        self._latched = False

    def _halted(self):
        if self._latched:
            return True
        if not self.safety.path.exists():
            return False
        try:
            return self.safety.read()['status'] != 'READY'
        except (OSError, ValueError, KeyError):
            return True

    def _latch(self, reason, result):
        """Halt progression. Never raises: a latch failure must not block restoration."""
        self._latched = True
        try:
            self.safety._write({'status': 'HALTED', 'reason': reason, 'time': time.time()})
        except (OSError, RuntimeError) as exc:
            result['latch_error'] = str(exc)

    def _record(self, result):
        try:
            self.audit.append({**result, 'time': time.time()})
            return True
        except OSError as exc:
            result['audit_error'] = str(exc)
            self._latch('audit_failure', result)
            return False

    def begin(self, rule, profile='adversarial'):
        if self._halted():
            return {'decision': 'HALTED', 'reason': 'explicit_recovery_required'}
        route = self.store.read()
        if route['status'] == 'CANARY':
            raise ValueError('rollout already active')
        if version(rule) == version(route['stable']):
            raise ValueError('candidate has same version as stable')
        functional = functional_gate(rule, Worker())
        performance = performance_gate(rule, Worker(), profile=profile) if functional['decision'] == 'PASS' else None
        gates = {'functional': functional, 'performance': performance}
        if functional['decision'] != 'PASS' or performance['decision'] != 'PASS':
            result = {'status': 'REJECTED', 'gates': gates}
            self._record({'decision': 'REJECTED', 'gates': gates}) or result.update(audit_error=True)
            return result
        return self.store.update(route['epoch'], candidate=rule, original=route['stable'],
                                 percent=10, stage=0, status='CANARY', minimum=self.minimum,
                                 started=time.time(), gates=gates)

    def observe(self, observations):
        if self._halted():
            return {'decision': 'HALTED', 'reason': 'explicit_recovery_required'}
        route = self.store.read()
        if route['status'] != 'CANARY':
            return {'decision': 'NOOP', 'status': route['status']}
        if time.time() - route['started'] > 120:
            result = {'decision': 'INCONCLUSIVE', 'reason': 'stage_deadline',
                      'rollback': self.rollback('stage_deadline', expected=route['epoch'])}
            self._record(result)
            return result
        if any(not isinstance(r, dict) for r in observations):
            result = {'decision': 'INCONCLUSIVE', 'reason': 'invalid_telemetry'}
            self._record(result)
            return result
        stage_rows = [r for r in observations if r.get('epoch') == route['epoch']]
        result = assess(stage_rows, version(route['original']), version(route['candidate']),
                        minimum=route['minimum'])
        result.update(epoch=route['epoch'], percent=route['percent'], time=time.time())
        recorded = self._record(result)
        if result['decision'] == 'REJECT':
            # Restore even when the decision could not be audited; but an unaudited
            # decision keeps the latch until an operator recovers explicitly.
            result['rollback'] = self.rollback(result['reason'], expected=route['epoch'],
                                               clear=recorded)
        elif result['decision'] == 'PASS' and not recorded:
            result['route_unchanged'] = 'audit_failure'
        elif result['decision'] == 'PASS':
            if route['stage'] == 2:
                result['route'] = self.store.update(route['epoch'], stable=route['candidate'],
                                                    status='PROMOTED', percent=100)
            else:
                index = route['stage'] + 1
                result['route'] = self.store.update(route['epoch'], stage=index, percent=STAGES[index],
                                                    started=time.time())
        return result

    def rollback(self, reason, expected=None, clear=True):
        """Restore the original stable rule.

        The halt latch is persisted *before* touching the route, so a failure at
        any later step (lock deadline, lost state, readback mismatch) leaves
        progression stopped across restarts. The latch is cleared only after a
        verified restore whose audit record was also written.
        """
        started = time.monotonic()
        latch = {}
        self._latch(reason, latch)
        try:
            route = self.store.read()
            restored = self.store.update(route['epoch'] if expected is None else expected,
                                         stable=route['original'], candidate=None, percent=0,
                                         status='ROLLED_BACK')
            if version(restored['stable']) != version(route['original']) or restored['percent'] != 0:
                raise RuntimeError('rollback readback failed')
            result = {'decision': 'ROLLED_BACK', 'reason': reason, 'route': restored,
                      'recovery_ms': (time.monotonic() - started) * 1000}
        except (OSError, ValueError, KeyError, RuntimeError) as exc:
            result = {'decision': 'ROLLBACK_FAILED', 'reason': reason, 'error': str(exc)}
        result.update(latch)
        recorded = self._record(result)
        if result['decision'] == 'ROLLED_BACK' and recorded and clear and 'latch_error' not in result:
            try:
                self.safety._write({'status': 'READY', 'time': time.time()})
                self._latched = False
            except (OSError, RuntimeError) as exc:
                result['latch_error'] = str(exc)
        return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--state', required=True)
    parser.add_argument('--minimum', type=int, default=1000)
    parser.add_argument('command', choices=['init', 'begin', 'observe', 'rollback', 'state'])
    parser.add_argument('--rule', choices=RULES, default='good')
    parser.add_argument('--profile', choices=['adversarial', 'small'], default='adversarial')
    parser.add_argument('--metrics')
    args = parser.parse_args()
    store = Store(args.state)
    c = Controller(store, args.minimum)
    if args.command == 'init':
        result = store.initialize(RULES['stable'])
    elif args.command == 'begin':
        result = c.begin(RULES[args.rule], profile=args.profile)
    elif args.command == 'observe':
        result = c.observe(Journal(args.metrics).read())
    elif args.command == 'rollback':
        result = c.rollback('operator_requested')
    else:
        result = store.read()
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
