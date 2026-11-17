#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
if command -v gitleaks >/dev/null 2>&1; then
  scanner=$(command -v gitleaks)
elif [ -x "$HOME/.local/bin/gitleaks" ]; then
  scanner="$HOME/.local/bin/gitleaks"
else
  printf '%s\n' 'gitleaks is required; refusing to skip the secret scan.' >&2
  exit 2
fi
case "${1:-staged}" in
  staged) exec "$scanner" git --pre-commit --staged --redact --no-banner --timeout 30 . ;;
  all) exec "$scanner" dir --redact --no-banner --timeout 30 . ;;
  *) printf '%s\n' 'usage: scripts/secret-scan.sh [staged|all]' >&2; exit 2 ;;
esac
