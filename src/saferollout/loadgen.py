"""Finite serial HTTP load, matching traffic mix per version; no host stress loops."""
import argparse
from collections import Counter
import json
import time
import urllib.error
import urllib.request
import urllib.parse

from .metrics import Journal
from .router import Store, choose
from .rules import FIXTURES, version


def send(url, body):
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                 headers={'Content-Type': 'application/json'})
    started = time.monotonic()
    try:
        response = urllib.request.urlopen(req, timeout=2)
    except urllib.error.HTTPError as exc:
        response = exc
    with response:
        return {'http_status': response.status, 'response': json.load(response),
                'client_ms': (time.monotonic() - started) * 1000}


def run(url, state, output, minimum=100, seconds=90):
    if not 10 <= minimum <= 1000 or not 1 <= seconds <= 90:
        raise ValueError('load budget out of bounds')
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != 'http' or parsed.hostname != '127.0.0.1' or not parsed.port or parsed.path or parsed.username:
        raise ValueError('load target must be loopback HTTP origin')
    route = Store(state).read()
    stable = version(route['stable'])
    candidate = version(route['candidate']) if route['candidate'] else None
    targets = {stable, candidate} - {None}
    counts = Counter()
    journal = Journal(output)
    started = time.monotonic()
    sent = 0
    for i in range(12000):
        if time.monotonic() - started >= seconds or all(counts[v] >= minimum for v in targets):
            break
        rid = f'e{route["epoch"]}-load-{i}'
        control = route['percent'] == 100 and i % 2 == 0
        predicted = stable if control else choose(route, rid)
        # Same ordered fixture distribution in both cohorts; synthetic and intentional.
        text, expected = FIXTURES[counts[predicted] % len(FIXTURES)]
        try:
            row = send(url + ('/baseline' if control else '/inspect'),
                       {'request_id': rid, 'text': text, 'expected_block': expected})
        except (OSError, ValueError) as exc:
            journal.append({'status': 'transport_error', 'request_id': rid, 'error': str(exc)})
            break
        journal.append(row)
        sent += 1
        observed = row['response']
        if observed.get('status') != 'ok' or observed.get('version') != predicted:
            break
        counts[observed['version']] += 1
    return {'sent': sent, 'counts': dict(counts), 'minimum': minimum,
            'elapsed_s': time.monotonic() - started, 'epoch': route['epoch'],
            'decision': 'COMPLETE' if all(counts[v] >= minimum for v in targets) else 'INCONCLUSIVE'}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--url', required=True)
    p.add_argument('--state', required=True)
    p.add_argument('--output', required=True)
    p.add_argument('--minimum', type=int, default=100)
    p.add_argument('--seconds', type=int, default=90)
    args = p.parse_args()
    print(json.dumps(run(args.url, args.state, args.output, args.minimum, args.seconds)))


if __name__ == '__main__':
    main()
