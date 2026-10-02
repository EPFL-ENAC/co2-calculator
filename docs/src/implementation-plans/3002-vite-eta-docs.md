---
status: in-progress
issue: 3002
last_updated: 2026-10-02
summary: Exploratory third docs build, Vite + vite-ssr-i18n-basic + Eta with a Markdown-to-Eta converter, timed against MkDocs and Zensical. Not for merge as is.
---

# Docs site built with Vite and Eta (exploratory)

## Problem

[Plan 3002-zensical-docs](3002-zensical-docs.md) showed Zensical is no
faster than MkDocs here: both render with single-threaded Python-Markdown.
This variant tries a Node pipeline instead: `marked` for Markdown and the
`vite-ssr-i18n-basic` Vite plugin for pages, as on pierreguilbert.com.

## What it is

Everything lives in `docs/eta/`; the build in `docs/` is untouched.

- The plugin renders `docs/src/**/*.md` directly (`pagesDir: "../src"`),
  with the Markdown pages from the unreleased
  [plugin PR #5](https://github.com/guilbep/vite-ssr-i18n-basic/pull/5)
  (stacked on [#4](https://github.com/guilbep/vite-ssr-i18n-basic/pull/4)),
  pinned as a GitHub tarball of its head commit.
- `scripts/prepare.mjs` writes what the plugin cannot know: the section
  and plan indexes (a port of `gen_indexes.py`, byte-identical output,
  same non-zero exit on an unknown status), the sidebar nav from
  `zensical.toml` as `src/data/meta.json`, `routes.config.json`, and page
  images.
- `scripts/marked-extensions.mjs`: Python-Markdown heading ids, so
  `page.md#anchor` links keep working, and Mermaid blocks.
- The layout renders the nav from data with a recursive partial;
  `minifyHtml: false`.
- `Dockerfile` builds from the `docs/` context:
  `docker build -f docs/eta/Dockerfile docs/`.

## Measurements

About 380 source pages plus 4 generated indexes, Apple Silicon.

| Build                         | MkDocs | Zensical  | Vite + Eta |
| ----------------------------- | ------ | --------- | ---------- |
| Local, cold (no git plugins)  | 4.8 s  | 6.0–6.3 s | 0.7 s      |
| ↳ `prepare.mjs`               | n/a    | n/a       | 0.07 s     |
| ↳ `vite build`                | n/a    | n/a       | 0.6 s      |
| Local, cold, with HTML minify | n/a    | n/a       | 2.2 s      |
| Docker image, `--no-cache`    | 14.5 s | 14.2 s    | 6.1–6.8 s  |
| Docker, with HTML minify      | n/a    | n/a       | 8.8 s      |
| Image size                    | 74 MB  | 71 MB     | 44 MB      |
| Site size                     | 34 MB  | 33 MB     | 9.8 MB     |

The plugin's per-page `html-minifier-terser` took 1.5 s of a 1.8 s
`vite build` and saved 0.1 MB, so it is off. MkDocs and Zensical do not
minify either, which makes the main rows like for like on that point.

Part of the gap is doing less work. This variant has no search index,
no 404 page, no per-page table of contents, no Material theme, no
admonitions, footnotes or `attr_list` (one page each), and no syntax
highlighting (Zensical runs Pygments on 197 pages).

Markdown live reload works: under `npm run dev`, an edit to a page in
`docs/src/` is served on the next request, about a second later. The
indexes and nav are written once at start; restart for a new plan or a
nav change.

## Verification

- Same pages at the same paths as Zensical, minus `404.html`.
  `check_links.py dist`: 0 broken.
- Heading ids match Zensical on 358 of 386 pages. 27 differ only because
  Python-Markdown turns `#2487 text` (no space) into a heading and
  CommonMark does not; one archived plan gains a heading.
- A planted `status: draft` fails the converter.

## Plugin feedback

Filed as [guilbep/vite-ssr-i18n-basic#3](https://github.com/guilbep/vite-ssr-i18n-basic/issues/3).
[#4](https://github.com/guilbep/vite-ssr-i18n-basic/pull/4) (3.1.0):
`emitRootRedirect` (off for one locale), `minifyHtml`, render failures
fail the build, directory check at build start, no hardcoded `en`/`fr`,
no debug logs, `sharp` 0.35.5.
[#5](https://github.com/guilbep/vite-ssr-i18n-basic/pull/5): Markdown
pages. Still open: copying images next to pages, which `prepare.mjs`
does here.

## Decision

Open. Fastest of the three, but it trades features for speed. Adopting
it means plugin releases with #4 and #5, rebuilding search,
highlighting, the 404 page and admonitions, and deleting `gen_indexes.py`
for the port.
