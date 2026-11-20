"""Write the generated section indexes before Zensical builds the site.

Zensical runs no MkDocs plugins, so this is a plain pre-build step (see
build.sh). It writes `_index.md` files into `src/`, gitignored. The
implementation-plans index is grouped by frontmatter `status`; other
sections get an alphabetical list.

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
import tomllib
from pathlib import Path
from typing import Any

import frontmatter

DOCS_DIR = Path(__file__).resolve().parent
DOCS_SRC = DOCS_DIR / "src"
PLANS_DIR = DOCS_SRC / "implementation-plans"

# Differs from `index.md` by more than case, so it does not collide with a
# hand-written `index.md` on case-insensitive filesystems (macOS/Windows).
GENERATED_INDEX_NAME = "_index.md"

STATUS_ORDER = ("delivered", "in-progress", "abandoned", "uncategorized")
STATUS_LABEL = {
    "delivered": "Delivered",
    "in-progress": "In progress",
    "abandoned": "Abandoned",
    "uncategorized": "Uncategorized",
}

_ISSUE_PREFIX_RE = re.compile(r"^\s*#?\s*(\d+)")


def _repo_url() -> str:
    config = tomllib.loads((DOCS_DIR / "zensical.toml").read_text(encoding="utf-8"))
    return str(config["project"]["repo_url"]).rstrip("/")


def _issue_cell(issue: Any, repo_url: str) -> str:
    """Show the frontmatter value (`310-b`), link the numeric prefix."""
    text = str(issue or "").strip().lstrip("#")
    match = _ISSUE_PREFIX_RE.match(text)
    if not match:
        return text
    return f"[#{text}]({repo_url}/issues/{match.group(1)})"


def _title_from(meta: dict[str, Any], body: str, fallback: str) -> str:
    if meta.get("title"):
        return str(meta["title"])
    for line in body.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return fallback


def _section_index(section: str) -> str:
    rows = []
    for md in sorted((DOCS_SRC / section).glob("*.md")):
        if md.name.lower() in {"index.md", GENERATED_INDEX_NAME}:
            continue
        post = frontmatter.loads(md.read_text(encoding="utf-8"))
        title = _title_from(post.metadata, post.content, md.stem)
        rows.append(f"- [{title}]({md.name})")
    lines = [f"# {section.replace('-', ' ').title()} index", ""]
    lines.extend(rows or ["_No pages yet._"])
    return "\n".join(lines) + "\n"


def _plan_entry(md: Path) -> tuple[str, dict[str, Any]]:
    post = frontmatter.loads(md.read_text(encoding="utf-8"))
    status = str(post.metadata.get("status", "")).strip().lower() or "uncategorized"
    if status not in STATUS_ORDER:
        # A typo'd status would vanish into "Uncategorized" unnoticed.
        raise SystemExit(
            f"{md.name}: unknown plan status {status!r}, use one of "
            + ", ".join(STATUS_ORDER[:-1])
        )
    summary = str(post.metadata.get("summary", "")).replace("|", "\\|")
    return status, {
        "title": _title_from(post.metadata, post.content, md.stem),
        "issue": post.metadata.get("issue", ""),
        "last_updated": post.metadata.get("last_updated", ""),
        "summary": summary,
        "filename": md.relative_to(PLANS_DIR).as_posix(),
    }


def _plans_index() -> str:
    groups: dict[str, list[dict[str, Any]]] = {key: [] for key in STATUS_ORDER}
    # Archived plans stay in the index: an idea that was tried and rejected
    # is worth finding before someone proposes it again.
    plan_files = sorted(PLANS_DIR.glob("*.md")) + sorted(
        (PLANS_DIR / "archive").glob("*.md")
    )
    for md in plan_files:
        if md.name == GENERATED_INDEX_NAME:
            continue
        status, entry = _plan_entry(md)
        groups[status].append(entry)

    repo_url = _repo_url()
    total = sum(len(v) for v in groups.values())
    lines = [
        "# Implementation plans",
        "",
        f"Plans live in `docs/src/implementation-plans/`. {total} total.",
        "",
    ]
    for key in STATUS_ORDER:
        if not groups[key]:
            continue
        lines += [f"## {STATUS_LABEL[key]} ({len(groups[key])})", ""]
        lines += [
            "| Title | Issue | Last updated | Summary |",
            "| --- | --- | --- | --- |",
        ]
        for e in groups[key]:
            issue = _issue_cell(e["issue"], repo_url)
            lines.append(
                f"| [{e['title']}]({e['filename']}) | {issue} | {e['last_updated']} | {e['summary']} |"
            )
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    for section in ("architecture", "backend", "frontend"):
        index = DOCS_SRC / section / GENERATED_INDEX_NAME
        index.write_text(_section_index(section), encoding="utf-8")
    (PLANS_DIR / GENERATED_INDEX_NAME).write_text(_plans_index(), encoding="utf-8")


if __name__ == "__main__":
    main()
