#!/usr/bin/env bash
# What /commit runs before it will draft a commit plan here. This repo commits straight to main and
# has no CI, no build and no deploy script, so nothing else reads a change on its way in.
#
# It runs the conventions checker, then the pytest suite over every tool under tools/. A pass says
# the tests and the adopted convention rules hold; it says nothing about the tools' live behaviour
# against Notion, Google or Facebook, which no test here reaches, nor about style — there is no lint
# config, and adopting one is its own decision with its own baseline.
#
# Prerequisites are `python3` on PATH and the dev install (`pip install -e ".[browser,contacts,test]"`),
# in `.venv/` or in whichever python3 is on PATH.
# Their absence fails rather than skips: a check that cannot tell "passed" from "never ran" turns an
# open problem into a closed-looking one.
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT" || exit 2

status=0

# Buffer each step and print its detail only when it fails, so a pass is one line per step.
run() {
  local label="$1" out
  shift
  out="$(mktemp)"
  if "$@" >"$out" 2>&1; then
    echo "==> $label — $(tail -n 1 "$out")"
  else
    echo "==> $label — FAILED"
    cat "$out"
    status=1
  fi
  rm -f "$out"
}

# The suite runs under the repo's virtualenv when one exists, because a Homebrew python3 refuses
# `pip install` outright (PEP 668) and so never has pytest; the venv path differs per platform.
PY=python3
for candidate in .venv/bin/python .venv/Scripts/python.exe; do
  [ -x "$candidate" ] && PY="$candidate" && break
done

run "Conventions" python3 ~/.claude/conventions/check.py .
run "Tests" "$PY" -m pytest -q

exit "$status"
