#!/bin/sh
# Command sequence shown in docs/demo/saferollout-demo.cast (recorded with asciinema).
# Every line printed after "$ " is the exact command that runs next; output is unedited.
# Paths stay relative to the repository root so the recording exposes no home directory.
set -eu
cd "$(dirname "$0")/.."
run="${1:-.run/demo-recording-$(date -u +%Y%m%dT%H%M%SZ)}"
mkdir -p "$(dirname "$run")"
mkdir "$run"

show() {
    printf '\n\033[1;32m$\033[0m %s\n' "$*"
}

printf '\033[1mSafeRollout Lab: real tests, real loopback HTTP, real rollback\033[0m\n'

show python3 -m pytest -q -rp
python3 -m pytest -q -rp

# Full experiment: loopback API, separate load generator, fresh controller process per decision.
# Its one-line JSON stdout contains an absolute path, so it is kept in the run directory instead.
show ./scripts/demo.sh "$run/evidence" 100 '>' "$run/demo-stdout.json"
./scripts/demo.sh "$run/evidence" 100 > "$run/demo-stdout.json"

show python3 scripts/record-demo.py --report "$run/evidence/summary.json"
python3 scripts/record-demo.py --report "$run/evidence/summary.json"

show python3 - "$run/evidence/summary.json" "  # inline reader in scripts/demo-recording.sh"
python3 - "$run/evidence/summary.json" <<'EOF'
import json, sys
s = json.load(open(sys.argv[1]))
print('bad canary  :', s['bad_canary']['decision'], '->', s['bad_canary']['rollback']['decision'])
print('API stopped :', s['api_down_rollback']['decision'])
print('lock held   :', s['rollback_failure']['decision'], '-', s['rollback_failure'].get('error'))
print('recovery    :', s['operator_recovery']['decision'])
print('final route :', s['final_route']['status'])
EOF
printf '\nDone. Raw evidence: %s/evidence/\n' "$run"
