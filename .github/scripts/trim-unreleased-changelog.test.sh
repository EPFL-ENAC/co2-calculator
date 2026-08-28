#!/usr/bin/env bash
# Regression test for #2466: run in a throwaway git repo with only v1.4.3
# tagged, feed the script a CHANGELOG with two untagged entries stacked above
# it (the exact shape the bug produces), and assert they're dropped.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET="$SCRIPT_DIR/trim-unreleased-changelog.sh"

TMP_REPO="$(mktemp -d)"
trap 'rm -rf "$TMP_REPO"' EXIT

cd "$TMP_REPO"
git init -q
git commit -q --allow-empty -m "v1.4.3 commit"
git tag v1.4.3

cat > CHANGELOG.md <<'EOF'
## [1.5.1](https://example.com/compare/v1.0.7...v1.5.1) (2026-08-29)

### Bug Fixes

* untagged fix two

## [1.5.0](https://example.com/compare/v1.0.7...v1.5.0) (2026-08-28)

### Bug Fixes

* untagged fix one

## [1.4.3](https://example.com/compare/v1.0.7...v1.4.3) (2026-08-27)

### Bug Fixes

* released fix
EOF

"$TARGET" CHANGELOG.md

FIRST_HEADER="$(grep -m1 '^## \[' CHANGELOG.md)"
case "$FIRST_HEADER" in
  "## [1.4.3]"*)
    echo "PASS: unreleased 1.5.1/1.5.0 dropped, 1.4.3 is now first"
    ;;
  *)
    echo "FAIL: expected 1.4.3 header first, got: $FIRST_HEADER"
    exit 1
    ;;
esac

if grep -q '1.5.1\|1.5.0\|untagged fix' CHANGELOG.md; then
  echo "FAIL: unreleased content survived trimming"
  cat CHANGELOG.md
  exit 1
fi

if ! grep -q 'released fix' CHANGELOG.md; then
  echo "FAIL: released 1.4.3 content was dropped too"
  exit 1
fi

echo "PASS: all checks green"
