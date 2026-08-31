#!/usr/bin/env bash
# Refuse to let a credential enter a commit.
#
# This repo is public: a pushed commit is a publication, and a force-push does
# not take it back — GitHub keeps serving the blob by SHA until its own GC runs.
# Rotation is the only real remediation, so the cheap moment to catch a secret
# is before it is committed at all.
#
# Modes:
#   check-secrets.sh                 scan the staged diff (what lefthook runs)
#   check-secrets.sh --pending       scan everything uncommitted, staged or not
#   check-secrets.sh --files a b...  scan whole files
#   check-secrets.sh --stdin LABEL   scan stdin as the content of LABEL
#
# A line that legitimately holds a secret-shaped string (documentation, a test
# fixture) can carry a trailing `pragma: allowlist secret` marker. Use it for
# values that are genuinely not credentials — never to push a real one through.

set -uo pipefail

# Byte semantics: a UTF-8 locale makes awk abort on the first non-decodable
# byte, which would silently skip every file after it.
export LC_ALL=C

# Shared matcher. Each rule fires only when the captured value looks like a real
# secret rather than a placeholder, because a check people silence is no check.
read -r -d '' RULES <<'AWK'
function is_placeholder_host(h) {
  h = tolower(h)
  if (h ~ /^(localhost|127\.0\.0\.1|0\.0\.0\.0|\[?::1\]?|host|hostname|db|database|postgres|postgresql|mysql|mariadb|redis|minio|mongo|mongodb|rabbitmq|host\.docker\.internal)$/) return 1
  if (h ~ /(^|\.)(local|test|invalid|example|example\.com|localhost)$/) return 1
  if (h ~ /^[<${%(]/) return 1
  if (h ~ /^(your|my|some|the)[-_.]/) return 1
  return 0
}

function is_placeholder_secret(s, minlen,   low) {
  if (length(s) < minlen) return 1
  if (s ~ /^[<${%(]/) return 1
  if (s ~ /\*\*|xxx|XXX|\.\.\./) return 1
  low = tolower(s)
  if (low ~ /pass|pwd|secret|token|key|cred|changeme|example|placeholder|redacted|dummy|sample|fake|test|foo|bar|abc123|123456|deadbeef|hunter2/) return 1
  return 0
}

# Lines that read a secret from somewhere else are not lines that contain one.
function is_indirect(txt) {
  return (txt ~ /getenv|environ|process\.env|Deno\.env|System\.getenv|secretKeyRef|valueFrom|configMapKeyRef|\{\{|\$\{|<%=|%\(|:\?/)
}

function report(path, ln, rule, detail) {
  printf "%s:%s: %s — %s\n", path, ln, rule, detail > "/dev/stderr"
  hits++
}

function check(path, ln, txt,   m, at, colon, cred, host, sec, val) {
  if (txt ~ /pragma:[ \t]*allowlist[ \t]+secret/) return

  # A URL carrying inline credentials, pointed at a host that is not local.
  if (match(txt, /[a-zA-Z][a-zA-Z0-9+.-]*:\/\/[^\/:@ \t"'`<>]+:[^\/@ \t"'`<>]+@[A-Za-z0-9._-]+/)) {
    m = substr(txt, RSTART, RLENGTH)
    sub(/^[a-zA-Z][a-zA-Z0-9+.-]*:\/\//, "", m)
    at = index(m, "@")
    cred = substr(m, 1, at - 1)
    host = substr(m, at + 1)
    colon = index(cred, ":")
    sec = substr(cred, colon + 1)
    if (!is_placeholder_host(host) && !is_placeholder_secret(sec, 8))
      report(path, ln, "connection string with an inline password", "host " host)
  }

  # An assignment whose name says secret and whose value looks like one.
  # A generated secret nearly always mixes digits with letters; prose, slugs and
  # `token = some.module.call` do not, and that one condition is what separates
  # a real value from the surrounding code.
  if (!is_indirect(txt) &&
      match(txt, /(pass(word|wd)?|pwd|secret|token|api[_-]?key|access[_-]?key|auth[_-]?token|client[_-]?secret)[^A-Za-z0-9\n]{0,3}[:=][ \t]*["'`]?[A-Za-z0-9_\/+.=~-]{16,}/)) {
    val = substr(txt, RSTART, RLENGTH)
    sub(/^.*[:=][ \t]*["'`]?/, "", val)
    if (val ~ /[0-9]/ && val ~ /[A-Za-z]/ &&
        val !~ /^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)+$/ &&
        !is_placeholder_secret(val, 16))
      report(path, ln, "hardcoded secret assignment", "value of length " length(val))
  }

  if (txt !~ /X-Amz-(Credential|Signature)|githubusercontent/ && match(txt, /AKIA[0-9A-Z]{16}/))
    report(path, ln, "AWS access key id", substr(txt, RSTART, 8) "...")

  if (txt ~ /-----BEGIN([ A-Z]+)? PRIVATE KEY-----/)
    report(path, ln, "private key block", "inline PEM private key")

  if (txt !~ /githubusercontent|\?jwt=/ && txt ~ /eyJ[A-Za-z0-9_-]{15,}\.eyJ[A-Za-z0-9_-]{15,}\./)
    report(path, ln, "JSON Web Token", "signed JWT literal")

  if (match(txt, /gh[pousr]_[A-Za-z0-9]{36}/))
    report(path, ln, "GitHub token", substr(txt, RSTART, 4) "...")

  if (match(txt, /xox[baprs]-[0-9A-Za-z-]{20,}/))
    report(path, ln, "Slack token", substr(txt, RSTART, 5) "...")
}
AWK

# The staged diff is exactly the content entering the commit: added lines only,
# so an existing oddity elsewhere in a touched file never blocks an unrelated
# change, and a brand-new file is covered in full.
scan_staged_diff() {
  git diff --cached --unified=0 --no-color --diff-filter=ACMR |
    awk "$RULES"'
      /^\+\+\+ b\// { path = substr($0, 7); next }
      /^@@ / { split($3, h, ","); ln = substr(h[1], 2) + 0; next }
      /^\+/ { check(path, ln, substr($0, 2)); ln++; next }
      END { exit hits > 0 }
    '
}

scan_files() {
  [ "$#" -eq 0 ] && return 0
  awk "$RULES"'{ check(FILENAME, FNR, $0) } END { exit hits > 0 }' "$@"
}

# Everything not yet committed, staged or not. `git add` runs before content
# reaches the index, so a check that only reads the index sees nothing.
scan_pending() {
  local rc=0
  { git diff --cached --unified=0 --no-color --diff-filter=ACMR
    git diff --unified=0 --no-color --diff-filter=ACMR
  } | awk "$RULES"'
      /^\+\+\+ b\// { path = substr($0, 7); next }
      /^@@ / { split($3, h, ","); ln = substr(h[1], 2) + 0; next }
      /^\+/ { check(path, ln, substr($0, 2)); ln++; next }
      END { exit hits > 0 }
    ' || rc=1
  local -a untracked=()
  local f
  while IFS= read -r f; do [ -n "$f" ] && untracked+=("$f"); done \
    < <(git ls-files --others --exclude-standard)
  [ "${#untracked[@]}" -gt 0 ] && { scan_files "${untracked[@]}" || rc=1; }
  return "$rc"
}

scan_stdin() {
  awk -v label="$1" "$RULES"'{ check(label, FNR, $0) } END { exit hits > 0 }'
}

case "${1:---staged}" in
  --staged) scan_staged_diff ;;
  --pending) scan_pending ;;
  --files) shift; scan_files "$@" ;;
  --stdin) scan_stdin "${2:-<stdin>}" ;;
  *) scan_files "$@" ;;
esac

status=$?
if [ "$status" -ne 0 ]; then
  cat >&2 <<'MSG'

Refusing to continue: the content above looks like a live credential.

This repository is public. Committing publishes the secret, and a later
force-push does not unpublish it — rotation is the only remediation.

Read the credential from the environment instead:
    : "${DEV_URL:?set DEV_URL to the remote DSN (do not commit it)}"

If the match is genuinely not a credential, append `pragma: allowlist secret`
to that line so the exception is visible in review.
MSG
fi
exit "$status"
