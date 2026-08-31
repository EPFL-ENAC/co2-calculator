#!/usr/bin/env bash
# conventional-changelog always diffs from the latest git *tag*. Tags are cut
# later, at the stage -> main promotion (release-please.yml), so every
# dev -> stage run in between regenerates against the same stale tag and
# prepends a fresh, ever-growing diff on top of whatever the previous
# untagged run already wrote -- instead of replacing it. That's the
# overlapping-blocks bug in #2466 (recurrence of #2352).
#
# Fix: before regenerating, drop every CHANGELOG.md entry above the first one
# whose version already has a real `vX.Y.Z` tag. Those entries were never
# released (no tag = never promoted to main), so the next conventional-changelog
# run recomputes them anyway as part of one clean diff from the last real tag.
set -euo pipefail

CHANGELOG="${1:-CHANGELOG.md}"
[ -f "$CHANGELOG" ] || exit 0

awk '
  /^## \[?[0-9]+\.[0-9]+\.[0-9]+/ {
    if (!keep) {
      match($0, /[0-9]+\.[0-9]+\.[0-9]+/)
      version = substr($0, RSTART, RLENGTH)
      cmd = "git rev-parse -q --verify refs/tags/v" version " >/dev/null 2>&1"
      if (system(cmd) == 0) {
        keep = 1
      } else {
        print "trim-unreleased-changelog: dropping unreleased v" version " (no tag yet)" > "/dev/stderr"
        next
      }
    }
  }
  keep { print }
' "$CHANGELOG" > "$CHANGELOG.trimmed"

# No silent fallbacks: a tag-matching bug should fail loudly, not quietly
# wipe the file down to nothing.
if [ -s "$CHANGELOG" ] && [ ! -s "$CHANGELOG.trimmed" ]; then
  echo "trim-unreleased-changelog: would empty $CHANGELOG (no header matched an existing tag) -- refusing" >&2
  rm -f "$CHANGELOG.trimmed"
  exit 1
fi

mv "$CHANGELOG.trimmed" "$CHANGELOG"
