"""Fail if the built site has a dead relative link or image.

Zensical --strict only checks links to .md pages; this also catches dead
links to images and repository files. ponytail: drop when zensical does.
"""

import html
import pathlib
import re
import sys
import urllib.parse

site = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "site")
bad = total = 0
for page in site.rglob("*.html"):
    # Code samples show markup like `src="${url}x.js"`; that is text, not a link.
    text = re.sub(r"<code[^>]*>.*?</code>", "", page.read_text(), flags=re.S)
    for ref in re.findall(r'(?:href|src)="([^"#?]+)', text):
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
