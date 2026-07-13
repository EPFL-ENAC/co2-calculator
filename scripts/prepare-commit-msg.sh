#!/bin/sh
# Append the branch's issue number to the commit subject so time-tracking
# tools can attribute every commit: feat/1234-slug -> "subject (#1234)".
MSG_FILE="$1"
SOURCE="${2:-}"

case "$SOURCE" in merge|squash) exit 0 ;; esac

issue=$(git branch --show-current | sed -n 's|.*/\([0-9][0-9]*\).*|\1|p')
[ -n "$issue" ] || exit 0

# subject already references an issue -> leave it alone
head -1 "$MSG_FILE" | grep -qE '#[0-9]+' && exit 0

{ printf '%s (#%s)\n' "$(head -1 "$MSG_FILE")" "$issue"; tail -n +2 "$MSG_FILE"; } > "$MSG_FILE.tmp" \
  && mv "$MSG_FILE.tmp" "$MSG_FILE"
