#!/usr/bin/env python3
"""Fail when the code names EPFL, Accred or Entra (#3244).

Why this exists: another institution runs the same images, so an EPFL value
written in the code shows up in its app. Such a value comes back by a
copy-paste and no test sees it. This check finds the words in every tracked
file and in every new file that git does not ignore.

The exceptions are in scripts/institution-words-allowlist.txt, each with its
reason. Standard library only, so CI runs it without an install step.
"""

import fnmatch
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ALLOWLIST = ROOT / "scripts" / "institution-words-allowlist.txt"

# Case-sensitive on purpose: "accredited" and "Entrance" are plain words.
WORDS = re.compile(r"EPFL_TABLEAU|EPFL Tableau|EPFL|epfl|Accred|ACCRED|Entra(?![a-z])")
# Names of the project itself, not values of an institution: the GitHub
# organization and image registry that host the code, and the path of the
# EPFL deployment folder.
PROJECT_TOKENS = re.compile(
    r"EPFL-ENAC|epfl-enac|ghcr\.io/epfl-enac/epfl/|institutions/epfl\b"
)


def load_allowlist() -> list[tuple[str, set[str]]]:
    """Return (path glob, allowed words) pairs. "*" allows every word."""
    entries = []
    for number, raw in enumerate(ALLOWLIST.read_text().splitlines(), 1):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        parts = line.split(maxsplit=1)
        if len(parts) != 2:
            raise SystemExit(f"{ALLOWLIST.name} line {number}: expected 'glob words'")
        entries.append((parts[0], set(parts[1].split(","))))
    return entries


def listed_files() -> list[str]:
    output = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return [path for path in output.splitlines() if (ROOT / path).is_file()]


def allowed_words(path: str, allowlist: list[tuple[str, set[str]]]) -> set[str]:
    words: set[str] = set()
    for glob, entry_words in allowlist:
        if fnmatch.fnmatch(path, glob):
            words |= entry_words
    return words


def file_hits(path: str, allowed: set[str]) -> list[str]:
    data = (ROOT / path).read_bytes()
    if b"\0" in data:
        return []
    hits = []
    for number, line in enumerate(data.decode("utf-8", "replace").splitlines(), 1):
        for match in WORDS.finditer(PROJECT_TOKENS.sub("", line)):
            if match.group() not in allowed:
                hits.append(f"{path}:{number}: {match.group()}: {line.strip()[:120]}")
    return hits


def main() -> int:
    allowlist = load_allowlist()
    hits = []
    for path in listed_files():
        allowed = allowed_words(path, allowlist)
        if "*" not in allowed:
            hits.extend(file_hits(path, allowed))
    if hits:
        print("\n".join(hits))
        print(
            f"\n{len(hits)} institution word(s) in the code. Use a configuration "
            "value or a neutral word. A file that must name EPFL goes in "
            f"{ALLOWLIST.relative_to(ROOT)} with its reason."
        )
        return 1
    print("No EPFL, Accred or Entra written in the code.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
