#!/bin/bash

# Consolidate all open dependabot updates into a single local commit, then
# close the superseded PRs and produce a ready-to-use commit message.
#
# Workflow:
#   1. List all open dependabot PRs via gh.
#   2. For each PR, parse the structured `updated-dependencies:` YAML in
#      the head commit body and update direct dependencies in the
#      working-tree manifest files (preserving existing version specifiers).
#   3. Regenerate lockfiles (npm + uv) so they stay in sync with the
#      bumped manifests.
#   4. Check each PR against the working tree — if every direct dependency
#      it ships is now at-or-above target, the PR is superseded.
#   5. Comment + close those PRs on GitHub.
#   6. Write a commit message draft to .git/DEPENDABOT_CLOSED_MSG that
#      lists every closed PR, ready to use with `git commit -F`.
#
# Tradeoff: PRs are closed *before* the consolidation merges to dev.
# If you abandon the consolidation, you'll need to `gh pr reopen` them.
#
# Flags:
#   --dry-run         show what would happen, don't edit, install, or close
#   --yes, -y         skip the interactive confirmation prompt
#   --skip-install    skip lockfile regeneration (you'll need to run it manually)
#   --close-removed   also close PRs whose package is no longer in any manifest

set -e

DRY_RUN=0
ASSUME_YES=0
SKIP_INSTALL=0
CLOSE_REMOVED=0

while [ $# -gt 0 ]; do
    case "$1" in
        --dry-run) DRY_RUN=1; shift ;;
        --yes|-y) ASSUME_YES=1; shift ;;
        --skip-install) SKIP_INSTALL=1; shift ;;
        --close-removed) CLOSE_REMOVED=1; shift ;;
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

# =============================================================================
# Manifest editing
# =============================================================================

# update_npm_dep file pkg version → 0 if updated, 1 if pkg not present
update_npm_dep() {
    local file=$1 pkg=$2 version=$3
    [ -f "$file" ] || return 1

    local current
    current=$(python3 -c "
import json,sys
d=json.load(open('$file'))
for k in ('dependencies','devDependencies','optionalDependencies','peerDependencies'):
    v=d.get(k,{}).get('$pkg')
    if v: print(v); sys.exit(0)
" 2>/dev/null)

    [ -z "$current" ] && return 1

    local specifier="${current%%[0-9]*}"
    [ -z "$specifier" ] && specifier="="

    python3 - "$file" "$pkg" "${specifier}${version}" <<'PY'
import json, sys
path, pkg, new = sys.argv[1:]
with open(path) as f:
    data = json.load(f)
for k in ("dependencies","devDependencies","optionalDependencies","peerDependencies"):
    if pkg in data.get(k, {}):
        data[k][pkg] = new
with open(path, "w") as f:
    json.dump(data, f, indent=2)
    f.write("\n")
PY
    echo "    ✓ $file: $pkg → ${specifier}${version}"
    return 0
}

# update_toml_dep file pkg version → 0 if updated, 1 if pkg not present
update_toml_dep() {
    local file=$1 pkg=$2 version=$3
    [ -f "$file" ] || return 1

    local pkg_re
    pkg_re=$(printf '%s' "$pkg" | sed 's/[][\.^$*/+?(){}|]/\\&/g')

    if grep -qE "\"${pkg_re}(\[[^]]+\])?(==|>=|~=|=)[^\"]+\"" "$file"; then
        sed -i.bak -E "s#\"(${pkg_re}(\[[^]]+\])?)(==|>=|~=|=)[^\"]+\"#\"\1\3${version}\"#" "$file"
        rm -f "${file}.bak"
        echo "    ✓ $file: $pkg → $version"
        return 0
    fi
    return 1
}

# =============================================================================
# Parsing the dependabot commit body
# =============================================================================

# parse_updated_dependencies ref → tab-separated "name<TAB>version<TAB>type"
# lines, one per direct dependency in the commit body's YAML trailer.
parse_updated_dependencies() {
    local ref=$1
    git log -1 --format=%B "$ref" 2>/dev/null | awk '
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

target_set() {
    local branch=$1
    case "$branch" in
        */uv/*|*/pip/*) echo "toml" ;;
        */npm_and_yarn/*) echo "npm" ;;
        *) echo "any" ;;
    esac
}

# =============================================================================
# Working-tree dep satisfaction check
# Exit codes: 0=satisfied, 1=below target, 2=not declared
# =============================================================================

check_dep_in_working_tree() {
    local pkg=$1 target=$2

    python3 - "$pkg" "$target" "${NPM_FILES[@]}" "--" "${TOML_FILES[@]}" <<'PY'
import json, re, sys

pkg, target = sys.argv[1], sys.argv[2]
sep = sys.argv.index("--", 3)
npm_files = sys.argv[3:sep]
toml_files = sys.argv[sep + 1:]


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
    try:
        with open(f) as fh:
            data = json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError):
        continue
    for section in ("dependencies", "devDependencies", "optionalDependencies"):
        spec = data.get(section, {}).get(pkg)
        if spec:
            found = True
            if check_specifier(spec):
                satisfied = True

for f in toml_files:
    try:
        with open(f) as fh:
            content = fh.read()
    except FileNotFoundError:
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

# =============================================================================
# Step 1: Fetch open dependabot PRs and update manifests
# =============================================================================

echo "=== Step 1: Consolidating dependabot updates ==="
echo ""
echo "Refreshing remote refs..."
git fetch --all --prune > /dev/null 2>&1

PRS=$(gh pr list --author "app/dependabot" --state open \
    --json number,title,headRefName \
    --jq '.[] | "\(.number)\t\(.headRefName)\t\(.title)"')

if [ -z "$PRS" ]; then
    echo "No open dependabot PRs. Nothing to consolidate."
    exit 0
fi

declare -i UPDATED=0
declare -i SKIPPED=0
declare -a PR_INFO=()

while IFS=$'\t' read -r pr_num branch title; do
    [ -z "$pr_num" ] && continue
    PR_INFO+=("$pr_num"$'\t'"$branch"$'\t'"$title")

    set_kind=$(target_set "$branch")
    deps=$(parse_updated_dependencies "origin/$branch")

    if [ -z "$deps" ]; then
        echo "  • #$pr_num ($branch) — no parsable updates"
        continue
    fi

    echo "  • #$pr_num ($branch)"
    if [ "$DRY_RUN" -eq 1 ]; then
        while IFS=$'\t' read -r name version type; do
            [ -z "$name" ] && continue
            echo "    [dry-run] would update: $name → $version"
        done <<< "$deps"
        continue
    fi

    while IFS=$'\t' read -r name version type; do
        [ -z "$name" ] && continue
        local_updated=0
        if [ "$set_kind" = "toml" ] || [ "$set_kind" = "any" ]; then
            for f in "${TOML_FILES[@]}"; do
                if update_toml_dep "$f" "$name" "$version"; then
                    local_updated=1
                fi
            done
        fi
        if [ "$set_kind" = "npm" ] || [ "$set_kind" = "any" ]; then
            for f in "${NPM_FILES[@]}"; do
                if update_npm_dep "$f" "$name" "$version"; then
                    local_updated=1
                fi
            done
        fi
        if [ "$local_updated" -eq 1 ]; then
            UPDATED+=1
        else
            echo "    ↷ $name $version: not in any manifest (likely transitive)"
            SKIPPED+=1
        fi
    done <<< "$deps"
done <<< "$PRS"

echo ""
echo "Manifest changes: $UPDATED updated, $SKIPPED skipped"

if [ "$DRY_RUN" -eq 1 ]; then
    echo ""
    echo "=== DRY RUN — exiting before installs and PR closures ==="
    exit 0
fi

# =============================================================================
# Step 2: Regenerate lockfiles
# =============================================================================

if [ "$SKIP_INSTALL" -eq 0 ] && [ "$UPDATED" -gt 0 ]; then
    echo ""
    echo "=== Step 2: Regenerating lockfiles ==="

    if [ -f "package.json" ]; then
        echo "  → npm install (root)"
        npm install --package-lock-only --ignore-scripts >/dev/null
    fi
    if [ -f "frontend/package.json" ]; then
        echo "  → npm install (frontend)"
        (cd frontend && npm install --package-lock-only --ignore-scripts >/dev/null)
    fi
    if [ -f "frontend/storybook/package.json" ]; then
        echo "  → npm install (frontend/storybook)"
        (cd frontend/storybook && npm install --package-lock-only --ignore-scripts >/dev/null)
    fi
    if command -v uv >/dev/null; then
        if [ -f "backend/pyproject.toml" ]; then
            echo "  → uv lock (backend)"
            (cd backend && uv lock >/dev/null 2>&1)
        fi
        if [ -f "docs/pyproject.toml" ]; then
            echo "  → uv lock (docs)"
            (cd docs && uv lock >/dev/null 2>&1)
        fi
    else
        echo "  ⚠ uv not in PATH — skipping uv lockfile regen"
    fi
fi

# =============================================================================
# Step 3: Identify superseded PRs against the working tree
# =============================================================================

echo ""
echo "=== Step 3: Checking which PRs are superseded by the working tree ==="

declare -a CLOSABLE=()
declare -a HOLD=()

for entry in "${PR_INFO[@]}"; do
    pr_num=$(echo "$entry" | cut -f1)
    branch=$(echo "$entry" | cut -f2)
    title=$(echo "$entry" | cut -f3)

    deps=$(parse_updated_dependencies "origin/$branch")
    if [ -z "$deps" ]; then
        HOLD+=("#$pr_num — no parsable dependency block")
        continue
    fi

    all_satisfied=1
    missing=""
    while IFS=$'\t' read -r name version type; do
        [ -z "$name" ] && continue
        set +e
        check_dep_in_working_tree "$name" "$version"
        status=$?
        set -e
        case "$status" in
            0) ;;
            2) if [ "$CLOSE_REMOVED" -eq 1 ]; then
                   :
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
done

echo ""
echo "Will close: ${#CLOSABLE[@]}"
for entry in "${CLOSABLE[@]}"; do
    num=$(echo "$entry" | cut -f1)
    ttl=$(echo "$entry" | cut -f2)
    echo "  #$num — $ttl"
done
echo ""
echo "Left open: ${#HOLD[@]}"
for entry in "${HOLD[@]}"; do
    echo "  $entry"
done

if [ ${#CLOSABLE[@]} -eq 0 ]; then
    echo ""
    echo "No PRs to close. Manifest changes are staged in your working tree —"
    echo "commit them manually if you want to keep them."
    exit 0
fi

# =============================================================================
# Step 4: Confirm + close
# =============================================================================

echo ""
if [ "$ASSUME_YES" -ne 1 ]; then
    printf "Close %d PR(s) and write commit message? [y/N] " "${#CLOSABLE[@]}"
    read -r answer
    case "$answer" in
        y|Y|yes|YES) ;;
        *) echo "Aborted. No PRs were closed."; exit 0 ;;
    esac
fi

for entry in "${CLOSABLE[@]}"; do
    num=$(echo "$entry" | cut -f1)
    gh pr comment "$num" --body "Superseded by local consolidation of dependabot updates; the bump in this PR is already present in the working tree. Closing." >/dev/null
    gh pr close "$num" >/dev/null
    echo "  ✓ closed #$num"
done

# =============================================================================
# Step 5: Write commit message draft
# =============================================================================

GIT_DIR="$(git rev-parse --git-dir)"
MSG_FILE="$GIT_DIR/DEPENDABOT_CLOSED_MSG"
{
    echo "chore(deps): consolidate dependency updates"
    echo ""
    echo "Superseded ${#CLOSABLE[@]} dependabot PR(s):"
    echo ""
    for entry in "${CLOSABLE[@]}"; do
        num=$(echo "$entry" | cut -f1)
        ttl=$(echo "$entry" | cut -f2)
        echo "- #$num $ttl"
    done
} > "$MSG_FILE"

echo ""
echo "Commit message draft: $MSG_FILE"
echo ""
echo "Next steps:"
echo "  git add -A"
echo "  git commit -F $MSG_FILE"
