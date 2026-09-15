#!/usr/bin/env bash
# The raw `conventional-changelog` output is a flat list of commit subjects
# grouped by type (Bug Fixes / Features / ...) -- accurate, but not release
# notes anyone wants to read. The release runbook (docs/src/architecture/
# release-runbook.md, step 2) already documents rewriting the newest entry
# under three headings before it reaches `stage`; this automates that
# instead of relying on someone remembering to do it by hand.
#
# Fails soft: a missing key, a failed API call, or a malformed reply all
# leave the raw conventional-changelog entry untouched and just warn -- an
# ugly-but-working changelog beats a blocked promotion.
set -euo pipefail

CHANGELOG="${1:-CHANGELOG.md}"
MODEL="claude-haiku-4-5-20251001"

warn() { echo "::warning::curate-changelog: $1"; }

[ -f "$CHANGELOG" ] || { warn "no $CHANGELOG, skipping"; exit 0; }
[ -n "${ANTHROPIC_API_KEY:-}" ] || { warn "ANTHROPIC_API_KEY not set, leaving raw changelog"; exit 0; }

# First version header plus everything up to (not including) the second one --
# the same slice release-please.yml extracts for the GitHub Release body.
ENTRY="$(awk '/^## \[?[0-9]+\.[0-9]+\.[0-9]+/{c++; if (c == 2) exit} c == 1 {print}' "$CHANGELOG")"
[ -n "$ENTRY" ] || { warn "no version header found, leaving raw changelog"; exit 0; }

HEADER="$(printf '%s\n' "$ENTRY" | head -1)"
RAW_BODY="$(printf '%s\n' "$ENTRY" | tail -n +2)"
REST="$(awk '/^## \[?[0-9]+\.[0-9]+\.[0-9]+/{c++} c >= 2 {print}' "$CHANGELOG")"

read -r -d '' SYSTEM_PROMPT <<'EOF' || true
Rewrite the changelog entry below for a general engineering audience.
Reorganize its raw conventional-commit bullets under exactly these three
Markdown headings, in this order, using all three even if one ends up
empty (write "None." under it):

## Key Changes
## Bug Fixes
## Technical Improvements (Non-functional)

Rules:
- "Key Changes" = new features and behavior changes a user would notice.
- "Bug Fixes" = user-visible fixes.
- "Technical Improvements (Non-functional)" = performance, security,
  refactors, and test/CI/docs/dependency work -- everything else.
- Merge near-duplicate bullets about the same underlying change into one.
- Keep existing issue links like ([#1234](https://...)) where present;
  drop bare commit-hash links.
- Do not invent facts that are not in the input.
- Output only the rewritten Markdown, starting directly with
  "## Key Changes". No preamble, no code fences, no closing remarks.
EOF

REQUEST="$(jq -n --arg model "$MODEL" --arg system "$SYSTEM_PROMPT" --arg body "$RAW_BODY" \
  '{model: $model, max_tokens: 4096, system: $system, messages: [{role: "user", content: $body}]}')"

RESPONSE="$(curl -sS --fail-with-body https://api.anthropic.com/v1/messages \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -H "content-type: application/json" \
  -d "$REQUEST")" || { warn "Anthropic API call failed, leaving raw changelog"; exit 0; }

CURATED="$(printf '%s' "$RESPONSE" | jq -r '.content[0].text // empty')"

if [ -z "$CURATED" ] || ! printf '%s' "$CURATED" | grep -q '^## Key Changes'; then
  warn "curated changelog missing or malformed, leaving raw changelog"
  exit 0
fi

{
  printf '%s\n\n' "$HEADER"
  printf '%s\n\n' "$CURATED"
  printf '%s\n' "$REST"
} > "$CHANGELOG.curated"

mv "$CHANGELOG.curated" "$CHANGELOG"
