#!/usr/bin/env bash
# Exercises the three outcomes curate-changelog.sh cares about: no API key,
# a successful rewrite, and a malformed API reply. Mocks `curl` on PATH
# instead of calling Anthropic for real.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET="$SCRIPT_DIR/curate-changelog.sh"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

RAW_CHANGELOG='## [1.5.0](https://example.com/compare/v1.4.0...v1.5.0) (2026-09-15)


### Bug Fixes

* fix a thing ([#123](https://example.com/issues/123))

## [1.4.0](https://example.com/compare/v1.0.0...v1.4.0) (2026-08-01)


### Bug Fixes

* released fix
'

# --- Test 1: no API key -> file untouched -------------------------------
printf '%s' "$RAW_CHANGELOG" > "$TMP/CHANGELOG.md"
(unset ANTHROPIC_API_KEY; "$TARGET" "$TMP/CHANGELOG.md")
if ! diff -q <(printf '%s' "$RAW_CHANGELOG") "$TMP/CHANGELOG.md" >/dev/null; then
  echo "FAIL: missing-key case modified the changelog"
  exit 1
fi
echo "PASS: no API key leaves the raw changelog untouched"

# --- Test 2: successful curation splices the rewrite in -----------------
FAKE_BIN="$TMP/bin"
mkdir -p "$FAKE_BIN"
cat > "$FAKE_BIN/curl" <<'EOF'
#!/usr/bin/env bash
jq -n '{content: [{text: "## Key Changes\n\nNone.\n\n## Bug Fixes\n\n* fixed a thing ([#123](https://example.com/issues/123))\n\n## Technical Improvements (Non-functional)\n\nNone."}]}'
EOF
chmod +x "$FAKE_BIN/curl"

printf '%s' "$RAW_CHANGELOG" > "$TMP/CHANGELOG.md"
(export PATH="$FAKE_BIN:$PATH" ANTHROPIC_API_KEY="test-key"; "$TARGET" "$TMP/CHANGELOG.md")

if ! grep -q '^## \[1.5.0\]' "$TMP/CHANGELOG.md"; then
  echo "FAIL: version header lost"; cat "$TMP/CHANGELOG.md"; exit 1
fi
if ! grep -q '^## Key Changes' "$TMP/CHANGELOG.md"; then
  echo "FAIL: curated headings missing"; cat "$TMP/CHANGELOG.md"; exit 1
fi
if ! grep -q 'released fix' "$TMP/CHANGELOG.md"; then
  echo "FAIL: older, already-released entry was dropped"; exit 1
fi
if grep -q '### Bug Fixes' "$TMP/CHANGELOG.md" && [ "$(grep -c '^## \[1.5.0\]' "$TMP/CHANGELOG.md")" != "1" ]; then
  echo "FAIL: unexpected duplicate header"; exit 1
fi
echo "PASS: successful curation replaces the raw entry, keeps the header and older entries"

# --- Test 3: malformed API reply -> file untouched -----------------------
cat > "$FAKE_BIN/curl" <<'EOF'
#!/usr/bin/env bash
echo '{"content": [{"text": "not the expected shape"}]}'
EOF
chmod +x "$FAKE_BIN/curl"

printf '%s' "$RAW_CHANGELOG" > "$TMP/CHANGELOG.md"
(export PATH="$FAKE_BIN:$PATH" ANTHROPIC_API_KEY="test-key"; "$TARGET" "$TMP/CHANGELOG.md")
if ! diff -q <(printf '%s' "$RAW_CHANGELOG") "$TMP/CHANGELOG.md" >/dev/null; then
  echo "FAIL: malformed-reply case modified the changelog"
  exit 1
fi
echo "PASS: malformed reply leaves the raw changelog untouched"

echo "PASS: all checks green"
