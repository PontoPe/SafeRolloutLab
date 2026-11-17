import subprocess
import sys
import os
import json


def test_bounded_demo_uses_real_processes_and_http(tmp_path):
    env = {**os.environ, 'PYTHONPATH': 'src'}
    result = subprocess.run([sys.executable, '-m', 'saferollout.demo', '--output', str(tmp_path / 'run'),
                             '--minimum', '10'], env=env, capture_output=True, text=True, timeout=45)
    assert result.returncode == 0, result.stderr + result.stdout
    summary = json.loads((tmp_path / 'run' / 'summary.json').read_text())
    assert summary['good_final']['status'] == 'PROMOTED'
    assert summary['bad_canary']['rollback']['decision'] == 'ROLLED_BACK'
    assert summary['api_down_rollback']['decision'] == 'ROLLED_BACK'
    assert summary['rollback_failure']['decision'] == 'ROLLBACK_FAILED'
    assert summary['cleanup']['api_reaped'] is True
    assert summary['stage_minimum'] == 10
