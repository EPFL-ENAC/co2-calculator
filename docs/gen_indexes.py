"""Generate section and plan indexes before `zensical build`.

Zensical has no plugin API, so this runs as a plain script and writes
`_index.md` files next to the pages (gitignored). Implementation-plans index
is grouped by frontmatter `status` (delivered / in-progress / abandoned);
other sections get an alphabetical TOC. Files lacking frontmatter fall under
"Uncategorized". An unknown status exits non-zero.

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
import sys
import tomllib
from pathlib import Path
from typing import Any

import frontmatter


def _parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    post = frontmatter.loads(text)
    return dict(post.metadata), post.content


# Anchor paths to this script's directory so the script works in both layouts:
#   - local repo: <repo>/docs/gen_indexes.py with src/ as sibling
#   - Docker:     /app/gen_indexes.py with src/ as sibling (Dockerfile flattens docs/)
# The zensical.toml docs_dir = "src" declares the same sibling relationship.
DOCS_DIR = Path(__file__).resolve().parent
DOCS_SRC = DOCS_DIR / "src"
PLANS_DIR = DOCS_SRC / "implementation-plans"

# Filename for generated section/plan indexes. Differs from `index.md` by more
# than case so it does not collide with hand-authored `index.md` files on
# case-insensitive filesystems (macOS/Windows).
GENERATED_INDEX_NAME = "_index.md"


def _repo_url() -> str:
    """Return `repo_url` from zensical.toml, so issue links follow forks."""
    with (DOCS_DIR / "zensical.toml").open("rb") as f:
        return str(tomllib.load(f)["project"]["repo_url"]).rstrip("/")


_ISSUE_PREFIX_RE = re.compile(r"^\s*#?\s*(\d+)")


def _issue_cell(issue: Any, repo_url: str) -> str:
    """Render `issue` as a GitHub link when it has a numeric prefix.

    Display preserves the frontmatter value (e.g. ``310-b``) so sub-issue
    identifiers stay legible; the link target uses only the numeric prefix
    because GitHub issue URLs are integer-keyed.
    """
    text = str(issue or "").strip().lstrip("#")
    if not text:
        return ""
    match = _ISSUE_PREFIX_RE.match(text)
    if not match:
        return text
    return f"[#{text}]({repo_url}/issues/{match.group(1)})"


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
    (section_dir / GENERATED_INDEX_NAME).write_text("\n".join(lines) + "\n")


def _plans_index() -> list[str]:
    """Emit grouped index for implementation-plans; return status errors."""
    errors: list[str] = []
    if not PLANS_DIR.is_dir():
        return errors
    groups: dict[str, list[dict[str, Any]]] = {key: [] for key in STATUS_ORDER}
    # Archived plans are abandoned ones moved out of the way. They still
    # belong in the index: an idea that was tried and rejected is worth
    # finding before someone proposes it again.
    plan_files = sorted(PLANS_DIR.glob("*.md")) + sorted(
        (PLANS_DIR / "archive").glob("*.md")
    )
    for md in plan_files:
        meta, body = _parse_frontmatter(md.read_text(encoding="utf-8"))
        status = str(meta.get("status", "")).strip().lower() or "uncategorized"
        if status not in groups:
            # A typo'd or invented status would otherwise vanish into
            # "Uncategorized" unnoticed: collect it and fail the build.
            allowed = ", ".join(k for k in STATUS_ORDER if k != "uncategorized")
            errors.append(
                f"{md.name}: unknown plan status {status!r} — use one of {allowed}"
            )
            status = "uncategorized"
        groups[status].append(
            {
                "title": _title_from(meta, body, md.stem),
                "issue": meta.get("issue", ""),
                "last_updated": meta.get("last_updated", ""),
                "summary": meta.get("summary", ""),
                "filename": md.relative_to(PLANS_DIR).as_posix(),
            }
        )

    repo_url = _repo_url()
    lines = [
        "# Implementation plans",
        "",
        f"Plans live in `docs/src/implementation-plans/`. {sum(len(v) for v in groups.values())} total.",
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
            link = f"[{e['title']}]({e['filename']})"
            issue_link = _issue_cell(e["issue"], repo_url)
            summary = str(e["summary"]).replace("|", "\\|")
            lines.append(
                f"| {link} | {issue_link} | {e['last_updated']} | {summary} |"
            )
        lines.append("")

    (PLANS_DIR / GENERATED_INDEX_NAME).write_text("\n".join(lines) + "\n")
    return errors


for _section in ("architecture", "backend", "frontend"):
    _section_index(_section)
_errors = _plans_index()
if _errors:
    sys.exit("\n".join(_errors))
