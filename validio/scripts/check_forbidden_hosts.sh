#!/usr/bin/env bash
# Valio's real webshop must never be called. Fails when its hosts appear outside docs/.
# Nobody weakens this check.
set -uo pipefail
root="${1:-$(cd "$(dirname "$0")/.." && pwd)}"
. "$(dirname "$0")/_files.sh"
pattern='toimitustukku\.valioaimo\.fi|(^|[^a-z0-9.-])api\.valioaimo\.fi'
hits=0
while IFS= read -r f; do
  [ -f "$f" ] || continue
  case "$f" in "$root"/docs/*|*/scripts/check_forbidden_hosts.sh|*/tests/test_guards.py) continue ;; esac
  while IFS= read -r ln; do
    echo "FORBIDDEN HOST: $f:$ln"; hits=1
  done < <(grep -nIE "$pattern" "$f" 2>/dev/null | cut -d: -f1)
done < <(list_files "$root")
if [ "$hits" -ne 0 ]; then echo "check_forbidden_hosts: FAILED"; exit 1; fi
echo "check_forbidden_hosts: ok"
