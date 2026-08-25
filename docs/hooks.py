"""Turn links to repository source files into working GitHub links.

Plans routinely link to code — `backend/app/core/security.py`,
`frontend/src/stores/modules.ts`. Those are repository paths, not pages in
this site, so MkDocs cannot resolve them and the link renders dead. Sixty
such links existed across five pages.

Rewrite them to blob URLs on the repository's default branch. `HEAD` is
used rather than a branch name so the link keeps working when branches
come and go.

A link is only rewritten when it does **not** resolve to a page in this
site. `[Backend](backend/01-overview.md)` from the docs root is a real
page and must be left alone, even though it starts with `backend/`.
"""

from __future__ import annotations

import posixpath
import re
from typing import Any

# Top-level repository directories a doc might reference. `docs/` is
# deliberately absent: a link into the docs tree should stay relative so it
# renders as site navigation rather than bouncing the reader to GitHub.
REPO_DIRS = (
    "backend/",
    "frontend/",
    "helm/",
    "otel/",
    "scripts/",
    ".github/",
)

_LINK = re.compile(r"(\[[^\]]*\]\()([^)\s]+)(\))")


def on_page_markdown(
    markdown: str, page: Any, config: Any, files: Any, **_: Any
) -> str:
    repo_url = str(config.get("repo_url") or "").rstrip("/")
    if not repo_url:
        return markdown
    base = f"{repo_url}/blob/HEAD/"
    page_dir = posixpath.dirname(page.file.src_uri)

    def rewrite(match: re.Match[str]) -> str:
        target = match.group(2)
        if target.startswith(("http://", "https://", "#", "mailto:", "/")):
            return match.group(0)
        path = target.split("#")[0].split("?")[0]
        if not path or not path.startswith(REPO_DIRS):
            return match.group(0)
        # A page in this site wins over a repository file of the same path.
        if files.get_file_from_path(posixpath.normpath(posixpath.join(page_dir, path))):
            return match.group(0)
        return f"{match.group(1)}{base}{target}{match.group(3)}"

    return _LINK.sub(rewrite, markdown)
