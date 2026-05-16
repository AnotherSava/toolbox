#!/usr/bin/env bash
# repos-status.sh — list AnotherSava's git repos under PROJECTS_ROOT,
# sorted by last pushed commit date (descending). Prints a table to
# stdout and writes a CSV to the path given as $1 (default:
# tools/github/data/repos-status.csv relative to this script).
#
# Reads only local git state — no `git fetch` is run, so "last pushed"
# reflects what your local tracking refs already know about the remote.
#
# Environment overrides:
#   PROJECTS_ROOT — directory to scan (default /d/projects)
#   GITHUB_USER   — origin-URL owner to filter by (default AnotherSava)

set -euo pipefail

PROJECTS_ROOT="${PROJECTS_ROOT:-/d/projects}"
GITHUB_USER="${GITHUB_USER:-AnotherSava}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOOL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
OUTPUT_CSV="${1:-$TOOL_DIR/data/repos-status.csv}"

# Repos owned by $GITHUB_USER that should still be excluded from the report.
# See ../docs/findings.md for rationale.
EXCLUDED=(
  "notion"
  "claude-mermaid-fix"
)

is_excluded() {
  local rel="$1"
  for ex in "${EXCLUDED[@]}"; do
    [[ "$rel" == "$ex" ]] && return 0
  done
  return 1
}

mapfile -t git_dirs < <(
  find "$PROJECTS_ROOT" -maxdepth 4 -type d -name ".git" 2>/dev/null \
    | grep -v "/_archive/" \
    | grep -v "/node_modules/" \
    | sort
)

rows=()
for git_dir in "${git_dirs[@]}"; do
  repo="${git_dir%/.git}"
  rel="${repo#$PROJECTS_ROOT/}"
  is_excluded "$rel" && continue

  origin=$(git -C "$repo" remote get-url origin 2>/dev/null || true)
  [[ "$origin" =~ github\.com[:/]${GITHUB_USER}/ ]] || continue

  branch=$(git -C "$repo" symbolic-ref --short HEAD 2>/dev/null || echo "(detached)")
  upstream=$(git -C "$repo" rev-parse --abbrev-ref --symbolic-full-name '@{upstream}' 2>/dev/null || true)
  if [[ -n "${upstream:-}" ]]; then
    sort_iso=$(git -C "$repo" log -1 --format=%cI "$upstream")
    pushed_date=$(git -C "$repo" log -1 --format=%cs "$upstream")
    unpushed=$(git -C "$repo" rev-list --count "$upstream..HEAD")
  else
    sort_iso="0000-00-00T00:00:00"
    pushed_date=""
    unpushed=""
  fi
  uncommitted=$(git -C "$repo" status --porcelain | wc -l | tr -d ' ')
  rows+=("$sort_iso|$rel|$branch|$pushed_date|$unpushed|$uncommitted")
done

IFS=$'\n' sorted=($(printf '%s\n' "${rows[@]}" | sort -r))
unset IFS

mkdir -p "$(dirname "$OUTPUT_CSV")"
{
  echo "project,branch,last_pushed,unpushed,uncommitted"
  for row in "${sorted[@]}"; do
    IFS='|' read -r _iso project branch pushed_date unpushed uncommitted <<< "$row"
    printf '"%s","%s","%s","%s","%s"\n' "$project" "$branch" "$pushed_date" "$unpushed" "$uncommitted"
  done
} > "$OUTPUT_CSV"

printf "%-32s | %-22s | %-12s | %-8s | %-11s\n" "PROJECT" "BRANCH" "LAST PUSHED" "UNPUSHED" "UNCOMMITTED"
printf -- '-%.0s' {1..100}; echo
for row in "${sorted[@]}"; do
  IFS='|' read -r _iso project branch pushed_date unpushed uncommitted <<< "$row"
  printf "%-32s | %-22s | %-12s | %-8s | %-11s\n" \
    "$project" "$branch" "${pushed_date:-—}" "${unpushed:-—}" "$uncommitted"
done

echo
echo "CSV written to: $OUTPUT_CSV"
