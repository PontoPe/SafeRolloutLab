#!/usr/bin/env python3
"""Record real commands as asciicast v2 using only the Linux Python stdlib."""
import argparse
import codecs
import errno
import hashlib
import json
import os
from pathlib import Path
import pty
import subprocess
import sys
import time


def report(path):
    summary = json.loads(Path(path).read_text())
    print('Measured outcomes (not simulated output):')
    for stage in summary['stages']:
        print(f"  {stage['percent']}% stage: {stage['evaluation']['decision']}")
    for key in ('false_positive', 'expensive_preflight', 'missing_telemetry',
                'insufficient_sample', 'bad_canary', 'api_down_rollback',
                'rollback_failure', 'operator_recovery'):
        row = summary[key]
        print(f"  {key}: {row.get('decision', row.get('status'))}")
    print('  bad HTTP:', summary['bad_http']['http_status'])
    print('  post-rollback HTTP:', summary['post_rollback_http']['http_status'])
    print('  observations:', summary['observed_requests'])
    print('  worker status counts:', summary['status_counts'])
    print('  cleanup:', summary['cleanup'])
    assert summary['cleanup']['api_reaped']
    assert summary['good_final']['status'] == 'PROMOTED'
    assert summary['bad_canary']['rollback']['decision'] == 'ROLLED_BACK'
    for relative, expected in summary['source_sha256'].items():
        assert hashlib.sha256(Path(relative).read_bytes()).hexdigest() == expected, relative
    print('  all runtime source hashes match this checkout')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', default='.run/recording-' + time.strftime('%Y%m%dT%H%M%SZ', time.gmtime()))
    parser.add_argument('--report')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    os.chdir(root)
    if args.report:
        report(args.report)
        return
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=False)
    cast = output / 'demo.cast'
    started = time.monotonic()
    commands = [
        [sys.executable, '-m', 'pytest', '-q'],
        ['./scripts/demo.sh', str(output / 'evidence'), '100'],
        [sys.executable, 'scripts/record-demo.py', '--report', str(output / 'evidence/summary.json')],
    ]
    with cast.open('w') as recording:
        recording.write(json.dumps({'version': 2, 'width': 120, 'height': 32,
                                    'timestamp': int(time.time()), 'title': 'SafeRollout Lab: real HTTP and rollback',
                                    'env': {'TERM': 'xterm-256color'}}) + '\n')

        def emit(text):
            recording.write(json.dumps([round(time.monotonic() - started, 6), 'o', text]) + '\n')
            recording.flush()
            print(text, end='', flush=True)

        for command in commands:
            emit('\r\n$ ' + ' '.join(command) + '\r\n')
            master, slave = pty.openpty()
            decoder = codecs.getincrementaldecoder('utf-8')(errors='replace')
            process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=slave, stderr=slave,
                                       env={**os.environ, 'PYTHONUNBUFFERED': '1', 'COLUMNS': '120'})
            os.close(slave)
            try:
                while True:
                    try:
                        chunk = os.read(master, 65536)
                    except OSError as exc:
                        if exc.errno != errno.EIO:
                            raise
                        break
                    if not chunk:
                        break
                    emit(decoder.decode(chunk))
                remainder = decoder.decode(b'', final=True)
                if remainder:
                    emit(remainder)
            finally:
                os.close(master)
            result = process.wait()
            emit(f'\r\n[exit {result}]\r\n')
            if result:
                raise SystemExit(result)
    print(f'Recording saved: {cast.resolve()}')


if __name__ == '__main__':
    main()
