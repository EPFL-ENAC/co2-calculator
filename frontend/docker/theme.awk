# Turns the institution theme file into theme.css (#3244).
#
# Why awk: the nginx alpine-slim image has no node, and the dev server and the
# tests run this same file, so the theme has one parser everywhere.
#
# Input: one "name: value" line per value, "#" starts a comment line.
# Output on stdout: ":root { --theme-<name>: <value>; ... }" and one
# @font-face rule per font weight. A font name takes a URL. Without it, the
# font comes from the fonts/ folder of the assets, which defaults to Geist.
# Any error goes to stderr with the line number and exits 1, so the container
# stops instead of serving a half-themed app.
#
# The names below are the whole contract. institution-default/theme.conf.example
# documents each one. scripts/check-theme-keys.mjs fails `make type-check`
# when the first list and the --theme-* names of the SCSS differ.

BEGIN {
  split("accent accent-hover accent-light accent-lighter " \
        "text text-muted surface border link highlight " \
        "validated validated-light success warning error " \
        "radius radius-lg", names, " ")
  for (i in names) known[names[i]] = 1
  # Font names are not CSS properties: @font-face cannot read var().
  split("font-regular font-medium font-bold", fonts, " ")
  weight["font-regular"] = 400
  weight["font-medium"] = 500
  weight["font-bold"] = 700
  for (i in fonts) {
    known[fonts[i]] = 1
    font[fonts[i]] = "/institution/fonts/" substr(fonts[i], 6) ".woff2"
  }
  required["accent"] = 1
  failed = 0
  count = 0
}

function fail(message) {
  printf "%s line %d: %s\n", FILENAME, FNR, message > "/dev/stderr"
  failed = 1
}

# \r: a theme.conf saved with Windows line endings.
/^[ \t\r]*(#|$)/ { next }

{
  colon = index($0, ":")
  if (colon == 0) { fail("expected \"name: value\""); next }
  name = substr($0, 1, colon - 1)
  value = substr($0, colon + 1)
  gsub(/^[ \t]+|[ \t\r]+$/, "", name)
  gsub(/^[ \t]+|[ \t\r]+$/, "", value)
  if (!(name in known)) { fail("unknown name \"" name "\""); next }
  if (name in seen) { fail("\"" name "\" is set twice"); next }
  if (value == "") { fail("\"" name "\" has no value"); next }
  # A value is pasted into CSS: refuse anything that could close the rule.
  if (value ~ /[;{}<]/) { fail("\"" name "\" has a forbidden character"); next }
  seen[name] = 1
  if (name in font) {
    # The URL goes inside url("..."): refuse what could end the string.
    if (value !~ /^(https:\/\/|\/)[^ \t"'()\\]+$/) {
      fail("\"" name "\" must be an https:// URL or a path that starts with /")
      next
    }
    font[name] = value
    next
  }
  order[++count] = name
  values[name] = value
}

END {
  for (name in required) {
    if (!(name in seen)) {
      printf "%s: \"%s\" is required\n", FILENAME, name > "/dev/stderr"
      failed = 1
    }
  }
  if (failed) exit 1
  print ":root {"
  for (i = 1; i <= count; i++) printf "  --theme-%s: %s;\n", order[i], values[order[i]]
  print "}"
  for (i = 1; i <= 3; i++) {
    name = fonts[i]
    printf "@font-face {\n  font-family: InstitutionFont;\n  src: url(\"%s\") format(\"woff2\");\n  font-weight: %d;\n  font-style: normal;\n  font-display: swap;\n}\n", font[name], weight[name]
  }
}
