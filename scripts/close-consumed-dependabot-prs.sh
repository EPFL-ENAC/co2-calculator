#!/bin/bash

# Close dependabot PRs whose dependency bumps have already landed on the
# default branch (e.g. via a consolidation commit produced by
# consolidate-dependabot-updates.sh).
#
# Behaviour:
#   - List all open dependabot PRs.
#   - For each PR, parse the structured `updated-dependencies:` YAML in
#     the PR body to learn which (package, version) pairs it ships.
#   - For each direct dependency, check whether the target version is
#     already present in our local manifests on the current branch. If
#     EVERY direct dependency in the PR is already at-or-above the
#     dependabot version, comment + close the PR.
#   - Otherwise, leave the PR alone and report why.
#
# Flags:
#   --dry-run         show what would happen, don't comment or close
#   --branch REF      compare against REF (default: origin/dev — the
#                     branch dependabot targets in this repo)
#   --close-removed   also close PRs whose package is no longer present
#                     in any manifest (treat "absent" as "satisfied")
#   --yes             skip the interactive confirmation prompt

set -e

DRY_RUN=0
COMPARE_REF="origin/dev"
ASSUME_YES=0
CLOSE_REMOVED=0

while [ $# -gt 0 ]; do
    case "$1" in
        --dry-run) DRY_RUN=1; shift ;;
        --branch) COMPARE_REF="$2"; shift 2 ;;
        --close-removed) CLOSE_REMOVED=1; shift ;;
        --yes|-y) ASSUME_YES=1; shift ;;
        *) echo "Unknown flag: $1" >&2; exit 2 ;;
    esac
done

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

command -v gh >/dev/null || { echo "gh CLI is required" >&2; exit 1; }
command -v python3 >/dev/null || { echo "python3 is required" >&2; exit 1; }

NPM_FILES=(
    "package.json"
    "frontend/package.json"
    "frontend/storybook/package.json"
)
TOML_FILES=(
    "backend/pyproject.toml"
    "docs/pyproject.toml"
)

# check_dep pkg target
# Exit codes:
#   0 — found at or above target version
#   1 — found, but below target
#   2 — not declared in any manifest
check_dep() {
    local pkg=$1
    local target=$2

    python3 - "$pkg" "$target" "$COMPARE_REF" "${NPM_FILES[@]}" "--" "${TOML_FILES[@]}" <<'PY'
import json, re, subprocess, sys

pkg, target, ref = sys.argv[1], sys.argv[2], sys.argv[3]
sep = sys.argv.index("--", 4)
npm_files = sys.argv[4:sep]
toml_files = sys.argv[sep + 1:]


def read_at_ref(path):
    try:
        return subprocess.check_output(
            ["git", "show", f"{ref}:{path}"], stderr=subprocess.DEVNULL
        ).decode()
    except subprocess.CalledProcessError:
        return None


def vtuple(v):
    v = re.sub(r"[^0-9.].*$", "", v)
    return tuple(int(x) for x in v.split(".") if x.isdigit())


target_v = vtuple(target)
found = False
satisfied = False


def check_specifier(spec):
    m = re.match(r"^[=^~><]*\s*(.+)$", spec)
    return bool(m) and vtuple(m.group(1)) >= target_v


for f in npm_files:
    content = read_at_ref(f)
    if not content:
        continue
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        continue
    for section in ("dependencies", "devDependencies", "optionalDependencies"):
        spec = data.get(section, {}).get(pkg)
        if spec:
            found = True
            if check_specifier(spec):
                satisfied = True

for f in toml_files:
    content = read_at_ref(f)
    if not content:
        continue
    pkg_re = re.escape(pkg)
    pat = rf'"({pkg_re})(\[[^\]]+\])?(==|>=|~=|=)([0-9][^"]*)"'
    for m in re.finditer(pat, content):
        found = True
        if vtuple(m.group(4)) >= target_v:
            satisfied = True

if satisfied:
    sys.exit(0)
if found:
    sys.exit(1)
sys.exit(2)
PY
}

# parse_pr_dependencies head_ref
# Emits one "name<TAB>version<TAB>type" line per direct dependency in the
# head commit message's `updated-dependencies:` YAML block (the structured
# trailer dependabot writes — present in commit messages, not PR bodies).
parse_pr_dependencies() {
    local ref=$1
    git log -1 --format=%B "origin/$ref" 2>/dev/null | awk '
        BEGIN { in_block=0; name=""; ver=""; type="" }
        /^updated-dependencies:/ { in_block=1; next }
        in_block && /^[^- ]/ { in_block=0 }
        !in_block { next }
        /^- dependency-name:/ {
            if (name != "" && ver != "" && type ~ /^direct:/) {
                print name "\t" ver "\t" type
            }
            name=""; ver=""; type=""
            sub(/^- dependency-name:[[:space:]]*/, "")
            gsub(/"/, "")
            name=$0
        }
        /^[[:space:]]+dependency-version:/ {
            sub(/^[[:space:]]+dependency-version:[[:space:]]*/, "")
            ver=$0
        }
        /^[[:space:]]+dependency-type:/ {
            sub(/^[[:space:]]+dependency-type:[[:space:]]*/, "")
            type=$0
        }
        END {
            if (name != "" && ver != "" && type ~ /^direct:/) {
                print name "\t" ver "\t" type
            }
        }
    '
}

echo "Refreshing remote refs..."
git fetch --all --prune > /dev/null 2>&1

echo "Comparing against: $COMPARE_REF"
[ "$DRY_RUN" -eq 1 ] && echo "Mode: dry-run (no changes)"
echo ""

PRS=$(gh pr list --author "app/dependabot" --state open --json number,title,headRefName --jq '.[] | "\(.number)\t\(.headRefName)\t\(.title)"')

if [ -z "$PRS" ]; then
    echo "No open dependabot PRs."
    exit 0
fi

declare -a CLOSABLE=()
declare -a HOLD=()

while IFS=$'\t' read -r pr_num branch title; do
    [ -z "$pr_num" ] && continue
    deps=$(parse_pr_dependencies "$branch")
    if [ -z "$deps" ]; then
        HOLD+=("#$pr_num — no parsable dependency block (skipping)")
        continue
    fi
    all_satisfied=1
    missing=""
    while IFS=$'\t' read -r name version type; do
        [ -z "$name" ] && continue
        set +e
        check_dep "$name" "$version"
        status=$?
        set -e
        case "$status" in
            0) ;;  # satisfied
            2) if [ "$CLOSE_REMOVED" -eq 1 ]; then
                   :  # treat absent as satisfied
               else
                   all_satisfied=0
                   missing="${missing}${missing:+, }$name (removed)"
               fi ;;
            *) all_satisfied=0
               missing="${missing}${missing:+, }$name@$version" ;;
        esac
    done <<< "$deps"
    if [ "$all_satisfied" -eq 1 ]; then
        CLOSABLE+=("$pr_num"$'\t'"$title")
    else
        HOLD+=("#$pr_num — still needs: $missing")
    fi
done <<< "$PRS"

echo "=== Already satisfied on $COMPARE_REF (will close) ==="
if [ ${#CLOSABLE[@]} -eq 0 ]; then
    echo "  (none)"
else
    for entry in "${CLOSABLE[@]}"; do
        num=$(echo "$entry" | cut -f1)
        ttl=$(echo "$entry" | cut -f2)
        echo "  #$num — $ttl"
    done
fi
echo ""
echo "=== Still pending (will be left open) ==="
if [ ${#HOLD[@]} -eq 0 ]; then
    echo "  (none)"
else
    for entry in "${HOLD[@]}"; do
        echo "  $entry"
    done
fi
echo ""

if [ "$DRY_RUN" -eq 1 ] || [ ${#CLOSABLE[@]} -eq 0 ]; then
    exit 0
fi

if [ "$ASSUME_YES" -ne 1 ]; then
    printf "Close %d PR(s)? [y/N] " "${#CLOSABLE[@]}"
    read -r answer
    case "$answer" in
        y|Y|yes|YES) ;;
        *) echo "Aborted."; exit 0 ;;
    esac
fi

for entry in "${CLOSABLE[@]}"; do
    num=$(echo "$entry" | cut -f1)
    gh pr comment "$num" --body "Superseded by consolidation commit on \`$COMPARE_REF\`; the dependency bump in this PR is already present. Closing." >/dev/null
    gh pr close "$num" >/dev/null
    echo "  ✓ closed #$num"
done
