#!/usr/bin/env bash
# Fails when a Valio key, a private key or a filled-in .env shows up in files that git would see.
# Prints file and line number, never the secret.
set -uo pipefail
root="${1:-$(cd "$(dirname "$0")/.." && pwd)}"
. "$(dirname "$0")/_files.sh"
pattern='junct_[A-Za-z0-9_-]{20,}|-----BEGIN [A-Z ]*PRIVATE KEY-----|AIza[0-9A-Za-z_-]{30,}|"d" *: *"[A-Za-z0-9_-]{40,}"'
hits=0
while IFS= read -r f; do
  [ -f "$f" ] || continue
  case "$f" in */scripts/check_no_secrets.sh) continue ;; esac
  if [ "$(basename "$f")" = ".env" ]; then echo "SECRET: $f is a .env file"; hits=1; continue; fi
  while IFS=: read -r ln _; do
    echo "SECRET: $f:$ln"; hits=1
  done < <(grep -nIE "$pattern" "$f" 2>/dev/null | cut -d: -f1 | sed 's/$/:/')
done < <(list_files "$root")
if [ "$hits" -ne 0 ]; then echo "check_no_secrets: FAILED"; exit 1; fi
echo "check_no_secrets: ok"
