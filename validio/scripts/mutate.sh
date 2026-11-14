#!/usr/bin/env bash
# Mutation testing with mutmut on the modules that decide (see [tool.mutmut] in src/backend/pyproject.toml).
# It runs in a scratch copy under artifacts/mutmut/ (gitignored), never in the source tree, so a run leaves no
# mutants/ cache in git. One worker, one module after another, through $MUTATE_HEAVY when it is set.
# Usage from validio/:
#   make mutate                              every mutant without a result yet, then the score per file
#   make mutate MUTATE="run decide"          one module (decide, mandate, log, rank, substitute, claims)
#   make mutate MUTATE=score                 the score of the last run again (score -v lists survivors)
#   make mutate MUTATE="show NAME"           the diff of one mutant
#   make mutate MUTATE="retest NAME..."      run named mutants again, e.g. after adding a test
set -euo pipefail
root=$(cd "$(dirname "$0")/.." && pwd)
backend=$root/src/backend
# The copy sits one level below a mirror of validio/, so validio/config.py still finds ROOT, data/, docs/
# and scripts/ three levels up, the same as in the real tree.
mirror=$root/artifacts/mutmut/validio
work=$mirror/b
bin=$backend/.venv/bin
# MUTATE_HEAVY: a wrapper that runs one CPU-heavy command at a time on a shared machine (optional)
heavy=${MUTATE_HEAVY:-}
declare -A module=([decide]=policy.decide [mandate]=policy.mandate [log]=audit.log [rank]=matching.rank
                   [substitute]=matching.substitute [claims]=trust.claims)

sync() {
  mkdir -p "$mirror"
  for f in "$root"/* "$root"/.env; do
    case "$(basename "$f")" in artifacts) continue ;; esac
    [ -e "$f" ] && ln -sfn "$f" "$mirror/$(basename "$f")"
  done
  rsync -a --exclude .venv --exclude mutants --exclude __pycache__ --exclude .pytest_cache \
    --exclude .ruff_cache --exclude cloud --exclude frontend "$backend/" "$work/"
  # tests that look two levels up (src/) for cloud/ and frontend/ find them next to mutants/
  for f in "$root"/src/*; do
    [ "$(basename "$f")" = backend ] || ln -sfn "$f" "$work/$(basename "$f")"
  done
  # AuditLog.list shadows the builtin `list` in its class body; mutmut's copies of the methods then fail on
  # `-> list[...]`. Postponed annotations in the copy fix that without touching the source. Same mtime as
  # the source, so mutmut does not think the file changed.
  sed -i '1i from __future__ import annotations' "$work/validio/audit/log.py"
  touch -r "$backend/validio/audit/log.py" "$work/validio/audit/log.py"
  # mutmut maps tests to functions once and keeps the map; a function added since then would get no tests,
  # so every run maps again (one traced pass of the suite)
  rm -f "$work/mutants/mutmut-stats.json"
  # mutmut copies data files (policies.cedar, schemas) into mutants/ once and never again, so a policy change
  # would leave the suite failing in the copy; refresh them, the .py files mutmut regenerates itself
  if [ -d "$work/mutants/validio" ]; then
    rsync -a --exclude '*.py' --exclude '*.meta' --exclude '*.spans' --exclude __pycache__ \
      "$work/validio/" "$work/mutants/validio/"
  fi
}

mut() { (cd "$work" && $heavy "$bin/mutmut" "$@"); }

cmd=${1:-run}
[ $# -gt 0 ] && shift
case "$cmd" in
  run)
    sync
    # without a module: every mutant that has no result yet; with modules: those modules from scratch
    if [ $# -eq 0 ]; then mut run --max-children 1 | tr "\r" "\n" | tail -2; fi
    for one in "$@"; do mut run --max-children 1 "validio.${module[$one]}.*" | tr "\r" "\n" | tail -2; done
    (cd "$work" && "$bin/python" "$root/scripts/mutate_score.py") ;;
  sync) sync ;;
  retest) sync; mut run --max-children 1 "$@" | tr "\r" "\n" | tail -2 ;;
  score) cd "$work" && "$bin/python" "$root/scripts/mutate_score.py" "$@" ;;
  show) mut show "$1" ;;
  *) mut "$cmd" "$@" ;;
esac
