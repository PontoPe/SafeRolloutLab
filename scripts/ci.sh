#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
python3 -m pytest -q
python3 -m compileall -q src
exec scripts/secret-scan.sh all
