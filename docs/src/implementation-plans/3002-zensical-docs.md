---
status: in-progress
issue: 3002
last_updated: 2026-10-02
summary: Exploratory migration of the docs site from MkDocs to Zensical, with build-time measurements. Merge or abandon on the numbers.
---

# Migrate the docs site to Zensical (exploratory)

## Problem

The local docs build took 30 s, and `mkdocs serve` 60 s to start. The
ENAC-IT4R wiki already moved to [Zensical](https://zensical.org), the
successor to Material for MkDocs. Does the same move make our docs faster?

## What changed

- `docs/mkdocs.yml` → `docs/zensical.toml`, same nav, theme colours and
  Markdown extensions. The "classic" theme variant keeps Material's look.
- `gen_indexes.py` runs as a plain script before the build and writes the
  `_index.md` files to disk (gitignored). Zensical has no plugin API, so
  `mkdocs-gen-files` cannot run it. An unknown plan status now exits
  non-zero instead of relying on `--strict`.
- `hooks.py` is gone. Its 82 repository-file links (five plans) are
  rewritten once to GitHub `blob/HEAD/` URLs.
- `check_links.py` (from the wiki) fails the build on dead image and
  repository-file links; Zensical `--strict` only checks page links and
  anchors.
- Dropped: `git-authors`, `git-revision-date-localized` (Zensical cannot
  run them; the Docker image already skipped them), `minify`,
  `literate-nav` (no `SUMMARY.md`, it did nothing), the dead `pdf` target.
- `make build-docs` is the single build entry point: Makefile, Dockerfile
  and both CI workflows run it.

## Measurements

381 pages, Apple Silicon, Zensical 0.0.67.

| Build                                          | MkDocs   | Zensical  |
| ---------------------------------------------- | -------- | --------- |
| Local build, with git plugins (old default)    | 30 s     | n/a       |
| `serve` start, with git plugins (old default)  | 61 s     | n/a       |
| Local build, no git plugins, cold              | 4.8 s    | 6.0–6.3 s |
| Local build, warm, nothing changed             | no cache | 3.5–3.7 s |
| Local build, warm, one page edited             | no cache | 6.2 s     |
| `serve` start, no git plugins                  | 4.5 s    | not timed |
| Docker image, `--no-cache`                     | 14.5 s   | 14.2 s    |
| `make build-docs` (generate + build + checker) | n/a      | 7.0 s     |

MkDocs has no build cache: every build is a cold one. The 30 s and 61 s
come from the two git plugins, not from MkDocs. Like for like, Zensical
is no faster here: rendering is single-threaded Python-Markdown in both.
The index script (0.17 s) and the old hook (2 ms over all pages) are not
worth porting to Rust.

## Verification

- Same 386 HTML pages at the same URLs as the MkDocs build.
- Each check fails `make build-docs` when planted: dead `.md` link, dead
  anchor, dead image or `.py` link, `status: draft`, unparseable
  frontmatter.

## Decision

Open. `mkdocs serve` now prints a warning from the Material for MkDocs
team: MkDocs 2.0 removes the plugin system, rewrites theming and has no
migration path
([analysis](https://squidfunk.github.io/mkdocs-material/blog/2026/02/18/mkdocs-2.0/)).
Our build pins `mkdocs<1.7`, so it is frozen on 1.6 either way.

Merge for the lighter dependency set (13 locked packages instead of 46),
the wiki's toolchain and a maintained engine. Or abandon, and set
`MKDOCS_FULL_BUILD=false` as the local default instead (30 s → 5 s with
no migration).
