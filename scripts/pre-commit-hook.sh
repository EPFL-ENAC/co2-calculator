#!/usr/bin/env bash
set -e

# Get directories with staged files
staged_dirs=$(bash scripts/get-staged-dirs.sh)

if [ -z "$staged_dirs" ]; then
  echo "No staged files detected"
  exit 0
fi

echo "Detected changes in: $staged_dirs"

# Get staged files for passing to Makefiles
staged_files=$(git diff --cached --name-only --diff-filter=ACMR)

# Process each directory that has changes
for dir in $staged_dirs; do
  case "$dir" in
    backend)
      echo "Processing backend..."
      backend_files=$(echo "$staged_files" | grep "^backend/" | sed 's|^backend/||' | xargs)
      if [ -n "$backend_files" ]; then
        echo "Formatting backend files: $backend_files"
        (cd backend && make format FILES="$backend_files")
        echo "$staged_files" | grep "^backend/" | xargs -I {} git add {}
      fi
      ;;
    frontend)
      echo "Processing frontend..."
      frontend_files=$(echo "$staged_files" | grep "^frontend/" | sed 's|^frontend/||' | xargs)
      if [ -n "$frontend_files" ]; then
        (cd frontend && make format FILES="$frontend_files")
        echo "$staged_files" | grep "^frontend/" | xargs -I {} git add {}
      fi
      ;;
    docs)
      echo "Processing docs..."
      docs_files=$(echo "$staged_files" | grep "^docs/" | sed 's|^docs/||' | xargs)
      if [ -n "$docs_files" ]; then
        (cd docs && make format FILES="$docs_files")
        echo "$staged_files" | grep "^docs/" | xargs -I {} git add {}
      fi
      ;;
    helm)
      echo "Processing helm..."
      helm_files=$(echo "$staged_files" | grep "^helm/" | sed 's|^helm/||' | xargs)
      if [ -n "$helm_files" ]; then
        (cd helm && make format FILES="$helm_files")
        echo "$staged_files" | grep "^helm/" | xargs -I {} git add {}
      fi
      ;;
    root)
      echo "Processing root files..."
      root_files=$(echo "$staged_files" | grep -v "/" | xargs)
      if [ -n "$root_files" ]; then
        echo "$root_files" | xargs npx prettier --write --ignore-unknown
        echo "$root_files" | xargs git add
      fi
      ;;
  esac
done

echo "Pre-commit formatting complete!"