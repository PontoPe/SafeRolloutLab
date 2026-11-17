#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
export PYTHONPATH="$PWD/src${PYTHONPATH:+:$PYTHONPATH}"
output="${1:-.run/demo-$(date -u +%Y%m%dT%H%M%SZ)}"
exec python3 -m saferollout.demo --output "$output" --minimum "${2:-100}"
