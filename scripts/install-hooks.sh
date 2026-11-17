#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
# Local configuration only; never commit or change global Git configuration.
test -d .git || git init -q
mkdir -p .git/hooks
printf '%s\n' '#!/bin/sh' 'set -eu' 'exec "$(git rev-parse --show-toplevel)/scripts/secret-scan.sh" staged' > .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
printf '%s\n' 'Installed local fail-closed gitleaks pre-commit hook.'
