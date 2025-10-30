#!/bin/bash
# Get directories that have staged files
# Outputs space-separated list: "backend frontend docs helm root"

set -e

# Get all staged files
staged_files=$(git diff --cached --name-only --diff-filter=ACMR)

if [ -z "$staged_files" ]; then
  echo ""
  exit 0
fi

# Track which directories have changes
has_backend=0
has_frontend=0
has_docs=0
has_helm=0
has_root=0

# Check each staged file
while IFS= read -r file; do
  case "$file" in
    backend/*)
      has_backend=1
      ;;
    frontend/*)
      has_frontend=1
      ;;
    docs/*)
      has_docs=1
      ;;
    helm/*)
      has_helm=1
      ;;
    *)
      # Root-level files (like README.md, Makefile, etc.)
      has_root=1
      ;;
  esac
done <<< "$staged_files"

# Build output list
dirs=""
[ $has_backend -eq 1 ] && dirs="$dirs backend"
[ $has_frontend -eq 1 ] && dirs="$dirs frontend"
[ $has_docs -eq 1 ] && dirs="$dirs docs"
[ $has_helm -eq 1 ] && dirs="$dirs helm"
[ $has_root -eq 1 ] && dirs="$dirs root"

echo "$dirs" | xargs