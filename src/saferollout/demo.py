"""Executable local experiment; all request and performance observations are real."""
import argparse
from collections import Counter
import fcntl
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time

from .loadgen import send
from .metrics import Journal
from .router import Store, choose
from .rules import ADVERSARIAL, RULES, version


def experiment(output, minimum):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    state = output / 'route.json'
    metrics = output / 'metrics.jsonl'
    commands = Journal(output / 'commands.jsonl')
    processes = []
    summary = {'stage_minimum': minimum, 'proposed_minimum': 1000, 'calibration':
               'Serial fresh-interpreter requests; 100/version/stage for bounded shared-host demonstration. '
               'Default controller policy remains 1000; 10 is integration-test smoke only. '
               'Nearest-rank p95 only, no p99 or production statistical confidence.',
               'started_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
               'python': sys.version, 'platform': platform.platform(), 'git_commit': None,
               'synthetic_traffic': True, 'stages': [], 'worker_deadline_ms': 120}
    source = Path(__file__).resolve().parents[2]
    summary['source_sha256'] = {str(p.relative_to(source)): hashlib.sha256(p.read_bytes()).hexdigest()
                                for p in sorted((source / 'src').rglob('*.py'))}

    def command(module, *args, timeout=15):
        argv = [sys.executable, '-m', 'saferollout.' + module, *map(str, args)]
        result = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
        commands.append({'argv': argv, 'returncode': result.returncode,
                         'stdout': result.stdout, 'stderr': result.stderr, 'time': time.time()})
        if result.returncode:
            raise RuntimeError(result.stderr or result.stdout)
        return json.loads(result.stdout)

    def control(action, *args):
        return command('controller', '--state', state, '--minimum', minimum, action, *args)

    def start_api():
        ready = output / f'ready-{len(processes)}.json'
        logfile = open(output / f'api-{len(processes)}.log', 'w')
        p = subprocess.Popen([sys.executable, '-m', 'saferollout.api', '--state', str(state),
                              '--metrics', str(metrics), '--ready', str(ready)], stdout=logfile, stderr=logfile)
        processes.append((p, logfile))
        deadline = time.monotonic() + 5
        while not ready.exists():
            if p.poll() is not None or time.monotonic() > deadline:
                raise RuntimeError('API failed readiness')
            time.sleep(.01)
        return p, f'http://127.0.0.1:{json.loads(ready.read_text())["port"]}'

    def stop_api(p):
        if p.poll() is None:
            p.terminate()
            try:
                p.wait(timeout=3)
            except subprocess.TimeoutExpired:
                p.kill()
                p.wait(timeout=3)

    def load(url, label, amount):
        return command('loadgen', '--url', url, '--state', state, '--output', output / f'client-{label}.jsonl',
                       '--minimum', amount, '--seconds', 90, timeout=95)

    def observe():
        return control('observe', '--metrics', metrics)

    try:
        control('init')
        api, url = start_api()
        summary['baseline'] = load(url, 'baseline', 20)
        summary['false_positive'] = control('begin', '--rule', 'false-positive')
        summary['expensive_preflight'] = control('begin', '--rule', 'expensive')
        control('begin', '--rule', 'good')
        summary['missing_telemetry'] = observe()
        route = Store(state).read()
        send(url + '/inspect', dict(text='hello', request_id='insufficient-probe', expected_block=False))
        summary['insufficient_sample'] = observe()
        for stage in (10, 50, 100):
            generated = load(url, f'stage-{stage}', minimum)
            decision = observe()  # New controller OS process each time: persistence exercised.
            summary['stages'].append({'percent': stage, 'load': generated, 'evaluation': decision})
            if decision['decision'] != 'PASS':
                raise RuntimeError(f'good rule stage {stage} not approved: {decision}')
        summary['good_final'] = control('state')
        summary['promotion_replay'] = observe()
        control('begin', '--rule', 'expensive', '--profile', 'small')
        route = Store(state).read()
        bad_id = next(f'bad-{i}' for i in range(1000)
                      if choose(route, f'bad-{i}') == version(RULES['expensive']))
        stable_id = next(f'stable-{i}' for i in range(1000)
                         if choose(route, f'stable-{i}') == version(route['stable']))
        summary['comparable_stable_adversarial'] = send(url + '/inspect',
                dict(text=ADVERSARIAL, request_id=stable_id, expected_block=False))
        summary['bad_http'] = send(url + '/inspect',
                dict(text=ADVERSARIAL, request_id=bad_id, expected_block=False))
        summary['bad_canary'] = observe()
        summary['post_rollback_http'] = send(url + '/inspect',
                dict(text=ADVERSARIAL, request_id='rollback-readback', expected_block=False))
        control('begin', '--rule', 'stable')
        stop_api(api)
        summary['api_down_rollback'] = control('rollback')
        api, url = start_api()
        summary['restarted_api_http'] = send(url + '/inspect',
                dict(text='hello', request_id='api-restarted', expected_block=False))
        control('begin', '--rule', 'stable')
        with open(str(state) + '.lock', 'a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            summary['rollback_failure'] = control('rollback')
        summary['operator_recovery'] = control('rollback')
        summary['final_route'] = control('state')
        assert summary['good_final']['status'] == 'PROMOTED'
        assert summary['bad_canary']['rollback']['decision'] == 'ROLLED_BACK'
        assert summary['bad_http']['http_status'] == 503
        assert summary['post_rollback_http']['http_status'] == 200
        assert summary['api_down_rollback']['decision'] == 'ROLLED_BACK'
        assert summary['rollback_failure']['decision'] == 'ROLLBACK_FAILED'
    finally:
        for p, f in processes:
            stop_api(p)
            f.close()
        summary['cleanup'] = {'api_reaped': all(p.poll() is not None for p, _ in processes),
                              'api_pids': [p.pid for p, _ in processes]}
        summary['ended_utc'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        observed = Journal(metrics).read()
        summary['observed_requests'] = len(observed)
        summary['status_counts'] = dict(Counter(r['status'] for r in observed))
        summary['worker_cpu_ms_total'] = sum(r.get('cpu_ms') or 0 for r in observed)
        summary['candidate_requests'] = sum(r['candidate'] for r in observed)
        (output / 'summary.json').write_text(json.dumps(summary, indent=2, sort_keys=True) + '\n')
    return summary


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--output', required=True)
    p.add_argument('--minimum', type=int, default=100)
    args = p.parse_args()
    if not 10 <= args.minimum <= 1000:
        p.error('minimum must be 10..1000')
    summary = experiment(args.output, args.minimum)
    print(json.dumps({'output': str(Path(args.output).resolve()), 'requests': summary['observed_requests'],
                      'good': summary['good_final']['status'], 'cleanup': summary['cleanup']}))


if __name__ == '__main__':
    main()
