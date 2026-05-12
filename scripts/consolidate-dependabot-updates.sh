#!/bin/bash

# Consolidate all open dependabot updates into a single upgrade.
#
# Strategy: each dependabot commit body contains a structured
# `updated-dependencies:` YAML block with `dependency-name`,
# `dependency-version`, and `dependency-type`. We parse that block
# (not the branch name) so we get the correct package name and version
# even for scoped packages, packages with brackets, or grouped updates.
#
# For each direct dependency found, we locate it in one of the known
# manifest files and update the version in place, preserving the
# existing version specifier (=, ^, ~, >=, ==).

set -e

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

# Manifests we know how to update. Order matters for npm packages because
# a dep might appear in more than one workspace; we update every file
# where the package is found.
NPM_FILES=(
    "package.json"
    "frontend/package.json"
    "frontend/storybook/package.json"
)
TOML_FILES=(
    "backend/pyproject.toml"
    "docs/pyproject.toml"
)

echo "=== Consolidating Dependabot Updates ==="
echo ""
echo "Fetching all remote branches..."
git fetch --all --prune > /dev/null 2>&1
echo ""

# update_npm_dep file pkg version
# Sets the version of <pkg> in <file>'s dependencies/devDependencies
# if the package is currently declared there, preserving the specifier.
update_npm_dep() {
    local file=$1
    local pkg=$2
    local version=$3

    [ -f "$file" ] || return 1

    # Detect existing specifier so we keep ^/~/=/range.
    # Use python -c for safe JSON read; fall back to grep if python missing.
    local current
    current=$(python3 -c "
import json,sys
d=json.load(open('$file'))
for k in ('dependencies','devDependencies','optionalDependencies','peerDependencies'):
    v=d.get(k,{}).get('$pkg')
    if v: print(v); sys.exit(0)
" 2>/dev/null)

    if [ -z "$current" ]; then
        return 1
    fi

    # Preserve the leading specifier characters (^, ~, =, >=).
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
    echo "  ✓ $file: $pkg → ${specifier}${version}"
    return 0
}

# update_toml_dep file pkg version
# Updates "<pkg><op><old>" to "<pkg><op><new>" inside dependencies = [...]
# arrays. Handles bracketed extras like fastapi[standard].
update_toml_dep() {
    local file=$1
    local pkg=$2
    local version=$3

    [ -f "$file" ] || return 1

    # Escape regex metacharacters in the package name (brackets, dots).
    local pkg_re
    pkg_re=$(printf '%s' "$pkg" | sed 's/[][\.^$*/+?(){}|]/\\&/g')

    # Match "pkgname<op><any-version>" where <op> is one of ==, >=, ~=, ^=, =.
    # We capture the operator so we preserve it.
    if grep -qE "\"${pkg_re}(\[[^]]+\])?(==|>=|~=|=)[^\"]+\"" "$file"; then
        sed -i.bak -E "s#\"(${pkg_re}(\[[^]]+\])?)(==|>=|~=|=)[^\"]+\"#\"\1\3${version}\"#" "$file"
        rm -f "${file}.bak"
        echo "  ✓ $file: $pkg → $version"
        return 0
    fi
    return 1
}

# parse_updated_dependencies branch
# Emits one "name<TAB>version<TAB>type" line per direct dependency in the
# commit body's `updated-dependencies:` YAML block.
parse_updated_dependencies() {
    local branch=$1
    git log -1 --format=%B "$branch" 2>/dev/null | awk '
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

# Hint at which manifest set to try first, based on branch path.
target_set() {
    local branch=$1
    case "$branch" in
        */uv/*|*/pip/*) echo "toml" ;;
        */npm_and_yarn/*) echo "npm" ;;
        *) echo "any" ;;
    esac
}

declare -i UPDATED=0
declare -i SKIPPED=0

BRANCHES=$(git branch -r | sed 's/^[[:space:]]*//' | grep '^origin/dependabot/' | sed 's|^origin/||')

if [ -z "$BRANCHES" ]; then
    echo "No dependabot branches found."
    exit 0
fi

echo "Scanning dependabot branches:"
for branch in $BRANCHES; do
    set_kind=$(target_set "$branch")
    deps=$(parse_updated_dependencies "origin/$branch")

    if [ -z "$deps" ]; then
        echo "  • $branch — no parsable updates (skipped)"
        continue
    fi

    echo "  • $branch"
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
            echo "    ↷ $name $version: not found in any manifest (likely removed or transitive)"
            SKIPPED+=1
        fi
    done <<< "$deps"
done

echo ""
echo "=== Summary ==="
echo "Updated: $UPDATED dependency entries"
echo "Skipped: $SKIPPED (no matching manifest entry)"
echo ""
echo "Changed files:"
git status --short -- \
    package.json frontend/package.json frontend/storybook/package.json \
    backend/pyproject.toml docs/pyproject.toml 2>/dev/null || true
echo ""
echo "=== Next Steps ==="
echo "1. (root)             npm install"
echo "2. (frontend)         cd frontend && npm install"
echo "3. (backend)          cd backend && uv sync"
echo "4. (docs, if changed) cd docs && uv sync"
echo "5. Run tests, then commit."
echo ""
echo "After merging the consolidated commit, close the consumed PRs with:"
echo "  scripts/close-consumed-dependabot-prs.sh"
