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
#   PROJECTS_ROOT — directory to scan (overrides config/config.env)
#   GITHUB_USER   — origin-URL owner to filter by (default AnotherSava)
#
# On first run, if PROJECTS_ROOT is not set and config/config.env is
# missing, the script deduces PROJECTS_ROOT as the parent of the toolbox
# repo, asks for confirmation, and saves it to config/config.env.

set -euo pipefail

GITHUB_USER="${GITHUB_USER:-AnotherSava}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOOL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
CONFIG_FILE="$TOOL_DIR/config/config.env"
OUTPUT_CSV="${1:-$TOOL_DIR/data/repos-status.csv}"

if [[ -z "${PROJECTS_ROOT:-}" ]]; then
  if [[ -f "$CONFIG_FILE" ]]; then
    # shellcheck disable=SC1090
    source "$CONFIG_FILE"
  fi
fi

if [[ -z "${PROJECTS_ROOT:-}" ]]; then
  repo_root="$(cd "$TOOL_DIR/../.." && pwd)"
  deduced="$(dirname "$repo_root")"
  echo "No PROJECTS_ROOT set and no config at $CONFIG_FILE." >&2
  echo "Deduced from script location: $deduced" >&2
  read -r -p "Use this as PROJECTS_ROOT? [Y/n] " ans
  if [[ -z "$ans" || "$ans" =~ ^[Yy] ]]; then
    PROJECTS_ROOT="$deduced"
  else
    read -r -p "Enter PROJECTS_ROOT: " PROJECTS_ROOT
  fi
  mkdir -p "$(dirname "$CONFIG_FILE")"
  {
    echo "# github tool config — gitignored, user-specific"
    echo "PROJECTS_ROOT=\"$PROJECTS_ROOT\""
  } > "$CONFIG_FILE"
  echo "Wrote $CONFIG_FILE" >&2
fi

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

git_dirs=()
while IFS= read -r line; do
  git_dirs+=("$line")
done < <(
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
