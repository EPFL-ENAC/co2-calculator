"""Fail if the built site has a dead relative link or image.

ponytail: zensical has no link validation for non-page targets yet (a
link to `../../backend/x.py` renders dead); drop this when it does.
Copied from the ENAC-IT4R wiki, reading only real tags, so a `src="…"`
inside a code sample is not taken for a link.
"""

import html
import pathlib
import re
import sys
import urllib.parse

TAG = re.compile(r"<[a-zA-Z][^>]*>")
ATTR = re.compile(r'\s(?:href|src)="([^"#?]+)')

site = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "site")
bad = total = 0
for page in site.rglob("*.html"):
    for tag in TAG.findall(page.read_text()):
        for ref in ATTR.findall(tag):
            ref = html.unescape(ref)
            if ref.startswith(("http", "mailto:", "/", "javascript", "&", "data:")):
                continue
            total += 1
            target = (page.parent / urllib.parse.unquote(ref)).resolve()
            if not (target.exists() or (target / "index.html").exists()):
                bad += 1
                print(f"{page.relative_to(site)} -> {ref}")
print(f"{total} relative links, {bad} broken")
sys.exit(1 if bad else 0)
