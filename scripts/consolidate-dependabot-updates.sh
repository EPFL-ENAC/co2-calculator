#!/bin/bash

# Script to consolidate all dependabot updates into a single upgrade
# This script extracts dependency versions from remote dependabot branches and updates package files

set -e

echo "=== Consolidating Dependabot Updates ==="
echo ""

# Fetch all remote branches
echo "Fetching all remote branches..."
git fetch --all > /dev/null 2>&1
echo ""

# Arrays to store dependencies by location
declare -a ROOT_DEPS=()
declare -a FRONTEND_DEPS=()
declare -a BACKEND_PROD_DEPS=()
declare -a BACKEND_DEV_DEPS=()

# Get all dependabot branches
echo "Scanning dependabot branches..."
BRANCHES=$(git branch -r | grep "origin/dependabot/" | sed 's/origin\///')

for branch in $BRANCHES; do
    # Extract dependency info from branch name
    # Format: dependabot/{ecosystem}/{path}/{package}-{version}
    
    if [[ $branch == *"npm_and_yarn"* ]]; then
        # NPM/Yarn dependency
        # Extract package and version from branch like: dependabot/npm_and_yarn/frontend/dev/prettier-3.8.1
        if [[ $branch == *"frontend/"* ]]; then
            # Frontend dependency
            pkg_info=$(echo $branch | sed 's/dependabot\/npm_and_yarn\/frontend\///')
            pkg_name=$(echo $pkg_info | sed 's/\/dev\///' | sed 's/\/@.*\///' | sed 's/-[0-9].*//' | sed 's/@//')
            version=$(echo $pkg_info | grep -oE '[0-9]+\.[0-9]+\.[0-9]+(-[a-zA-Z0-9]+)?' | tail -1)
            
            # Handle scoped packages
            if [[ $pkg_info == *"@storybook/addon-docs"* ]]; then
                FRONTEND_DEPS+=("@storybook/addon-docs:$version")
            elif [[ $pkg_info == *"@types/node"* ]]; then
                FRONTEND_DEPS+=("@types/node:$version")
            else
                FRONTEND_DEPS+=("$pkg_name:$version")
            fi
        elif [[ $branch == *"dev/"* ]]; then
            # Root dev dependency
            pkg_info=$(echo $branch | sed 's/dependabot\/npm_and_yarn\/dev\///')
            pkg_name=$(echo $pkg_info | sed 's/-[0-9].*//')
            version=$(echo $pkg_info | grep -oE '[0-9]+\.[0-9]+\.[0-9]+(-[a-zA-Z0-9]+)?' | tail -1)
            ROOT_DEPS+=("$pkg_name:$version")
        fi
        
    elif [[ $branch == *"uv/backend"* ]]; then
        # UV/Python dependency
        pkg_info=$(echo $branch | sed 's/dependabot\/uv\/backend\///')
        pkg_name=$(echo $pkg_info | sed 's/\/dev\///' | sed 's/-[0-9].*//')
        version=$(echo $pkg_info | grep -oE '[0-9]+\.[0-9]+\.[0-9]+(-[a-zA-Z0-9]+)?' | tail -1)
        
        # Check if it's a dev dependency (in dev group) or production
        if [[ $branch == *"dev/"* ]]; then
            BACKEND_DEV_DEPS+=("$pkg_name:$version")
        else
            BACKEND_PROD_DEPS+=("$pkg_name:$version")
        fi
        
    elif [[ $branch == *"pip/backend"* ]]; then
        # Pip/Python dependency (production)
        # These branches have hash in name, skip or handle separately
        echo "  Skipping pip branch (hash-based): $branch"
    fi
done

echo ""
echo "Found dependencies to update:"
echo ""

# Update root package.json
if [ ${#ROOT_DEPS[@]} -gt 0 ]; then
    echo "📦 Root package.json:"
    for dep in "${ROOT_DEPS[@]}"; do
        pkg=$(echo $dep | cut -d: -f1)
        version=$(echo $dep | cut -d: -f2)
        echo "  - $pkg: ^$version"
        sed -i '' "s/\"$pkg\": \"\^[^\"]*\"/\"$pkg\": \"^$version\"/" package.json
    done
    echo ""
fi

# Update frontend package.json
if [ ${#FRONTEND_DEPS[@]} -gt 0 ]; then
    echo "🎨 frontend/package.json:"
    for dep in "${FRONTEND_DEPS[@]}"; do
        pkg=$(echo $dep | cut -d: -f1)
        version=$(echo $dep | cut -d: -f2)
        echo "  - $pkg: =$version"
        sed -i '' "s/\"$pkg\": \"[^\"]*\"/\"$pkg\": \"=$version\"/" frontend/package.json
    done
    echo ""
fi

# Update backend pyproject.toml (production dependencies)
if [ ${#BACKEND_PROD_DEPS[@]} -gt 0 ]; then
    echo "🐍 backend/pyproject.toml (production):"
    for dep in "${BACKEND_PROD_DEPS[@]}"; do
        pkg=$(echo $dep | cut -d: -f1)
        version=$(echo $dep | cut -d: -f2)
        echo "  - $pkg:==$version"
        sed -i '' "s/\"$pkg==[^\"]*\"/\"$pkg==$version\"/" backend/pyproject.toml
    done
    echo ""
fi

# Update backend pyproject.toml (dev dependencies)
if [ ${#BACKEND_DEV_DEPS[@]} -gt 0 ]; then
    echo "🔧 backend/pyproject.toml (dev):"
    for dep in "${BACKEND_DEV_DEPS[@]}"; do
        pkg=$(echo $dep | cut -d: -f1)
        version=$(echo $dep | cut -d: -f2)
        echo "  - $pkg:>=$version"
        sed -i '' "s/\"$pkg>=\[0-9.]*\"/\"$pkg>=$version\"/" backend/pyproject.toml
    done
    echo ""
fi

echo "=== Summary of Changes ==="
echo ""
echo "Root package.json:"
git diff package.json | grep "^[+-]" | grep -v "^[+-][+-][+-]" || echo "  No changes"
echo ""
echo "Frontend package.json:"
git diff frontend/package.json | grep "^[+-]" | grep -v "^[+-][+-][+-]" || echo "  No changes"
echo ""
echo "Backend pyproject.toml:"
git diff backend/pyproject.toml | grep "^[+-]" | grep -v "^[+-][+-][+-]" || echo "  No changes"
echo ""
echo "=== Next Steps ==="
echo "1. Run 'npm install' in root directory to update package-lock.json"
echo "2. Run 'npm install' in frontend directory to update frontend package-lock.json"
echo "3. Run 'uv sync' in backend directory to update uv.lock"
echo "4. Commit all changes with: git add -A && git commit -m 'chore: consolidate dependabot updates'"
echo ""
echo "✅ Done! All dependabot updates have been consolidated from remote branches."
