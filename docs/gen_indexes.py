"""Auto-index generator hook for MkDocs.

Walks documentation sections and emits virtual `INDEX.md` files via
`mkdocs_gen_files`. Implementation-plans index is grouped by frontmatter
`status` (delivered / in-progress / abandoned); other sections get an
alphabetical TOC. Files lacking frontmatter fall under "Uncategorized" so
`mkdocs build --strict` keeps passing before sibling backfill lands.

Frontmatter schema (all optional)::

    ---
    status: delivered | in-progress | abandoned
    issue: 310-b
    title: Human-readable title
    last_updated: 2026-05-05
    summary: One-line description.
    ---
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import mkdocs_gen_files

try:
    import frontmatter as _frontmatter

    def _parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
        post = _frontmatter.loads(text)
        return dict(post.metadata), post.content
except ImportError:  # minimal fallback parser
    _FM_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n(.*)\Z", re.DOTALL)

    def _parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
        match = _FM_RE.match(text)
        if not match:
            return {}, text
        meta: dict[str, Any] = {}
        for line in match.group(1).splitlines():
            if ":" not in line or line.lstrip().startswith("#"):
                continue
            key, _, value = line.partition(":")
            meta[key.strip()] = value.strip().strip("\"'")
        return meta, match.group(2)


# Anchor paths to this script's directory so the script works in both layouts:
#   - local repo: <repo>/docs/gen_indexes.py with src/ as sibling
#   - Docker:     /app/gen_indexes.py with src/ as sibling (Dockerfile flattens docs/)
# The mkdocs.yml docs_dir: src declares the same sibling relationship.
DOCS_DIR = Path(__file__).resolve().parent
DOCS_SRC = DOCS_DIR / "src"
PLANS_DIR = DOCS_SRC / "implementation-plans"

# Filename for generated section/plan indexes. Differs from `index.md` by more
# than case so it does not collide with hand-authored `index.md` files on
# case-insensitive filesystems (macOS/Windows).
GENERATED_INDEX_NAME = "_index.md"


def _plans_gh_url() -> str:
    """Derive the GitHub blob URL for implementation-plans from MkDocs config.

    Reads `repo_url` from the active MkDocs config (via `mkdocs_gen_files`),
    so fork builds and renamed remotes link correctly. Falls back to the
    upstream repo if config isn't available (e.g. running outside a build).
    """
    fallback = "https://github.com/epfl-enac/co2-calculator"
    try:
        repo_url = str(
            mkdocs_gen_files.FilesEditor.current().config.repo_url or fallback
        )
    except Exception:  # pragma: no cover - non-build invocation
        repo_url = fallback
    return f"{repo_url.rstrip('/')}/blob/main/docs/src/implementation-plans"

STATUS_ORDER = ("delivered", "in-progress", "abandoned", "uncategorized")
STATUS_LABEL = {
    "delivered": "Delivered",
    "in-progress": "In progress",
    "abandoned": "Abandoned",
    "uncategorized": "Uncategorized",
}


def _title_from(meta: dict[str, Any], body: str, fallback: str) -> str:
    if meta.get("title"):
        return str(meta["title"])
    for line in body.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return fallback


def _section_index(section: str) -> None:
    """Emit alphabetical TOC for a section under docs_dir."""
    section_dir = DOCS_SRC / section
    if not section_dir.is_dir():
        return
    rows = []
    skip_names = {"index.md", "index_.md", GENERATED_INDEX_NAME.lower()}
    for md in sorted(section_dir.glob("*.md")):
        if md.name.lower() in skip_names:
            continue
        meta, body = _parse_frontmatter(md.read_text(encoding="utf-8"))
        title = _title_from(meta, body, md.stem)
        rows.append(f"- [{title}]({md.name})")
    lines = [f"# {section.replace('-', ' ').title()} index", ""]
    lines.extend(rows or ["_No pages yet._"])
    with mkdocs_gen_files.open(f"{section}/{GENERATED_INDEX_NAME}", "w") as f:
        f.write("\n".join(lines) + "\n")


def _plans_index() -> None:
    """Emit grouped index for implementation-plans (lives under docs_dir/src)."""
    if not PLANS_DIR.is_dir():
        return
    groups: dict[str, list[dict[str, Any]]] = {key: [] for key in STATUS_ORDER}
    for md in sorted(PLANS_DIR.glob("*.md")):
        meta, body = _parse_frontmatter(md.read_text(encoding="utf-8"))
        status = str(meta.get("status", "")).strip().lower() or "uncategorized"
        if status not in groups:
            status = "uncategorized"
        groups[status].append(
            {
                "title": _title_from(meta, body, md.stem),
                "issue": meta.get("issue", ""),
                "last_updated": meta.get("last_updated", ""),
                "summary": meta.get("summary", ""),
                "filename": md.name,
            }
        )

    plans_gh_url = _plans_gh_url()
    lines = [
        "# Implementation plans",
        "",
        f"Plans live in `docs/src/implementation-plans/`; links point to GitHub. {sum(len(v) for v in groups.values())} total.",
        "",
    ]
    for key in STATUS_ORDER:
        entries = groups[key]
        if not entries:
            continue
        lines.append(f"## {STATUS_LABEL[key]} ({len(entries)})")
        lines.append("")
        lines.append("| Title | Issue | Last updated | Summary |")
        lines.append("| --- | --- | --- | --- |")
        for e in entries:
            link = f"[{e['title']}]({plans_gh_url}/{e['filename']})"
            summary = str(e["summary"]).replace("|", "\\|")
            lines.append(
                f"| {link} | {e['issue']} | {e['last_updated']} | {summary} |"
            )
        lines.append("")

    with mkdocs_gen_files.open(
        f"implementation-plans/{GENERATED_INDEX_NAME}", "w"
    ) as f:
        f.write("\n".join(lines) + "\n")


for _section in ("architecture", "backend", "frontend"):
    _section_index(_section)
_plans_index()
