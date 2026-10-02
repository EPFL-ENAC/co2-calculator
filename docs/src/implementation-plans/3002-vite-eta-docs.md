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

Everything lives in `docs/eta/`; the MkDocs-replacement build in `docs/`
is untouched.

- `scripts/build-pages.mjs` turns `docs/src/**/*.md` into
  `src/pages/**/*.eta`, after pierreguilbert.com's `build-blog.mjs`. It
  also writes the section and plan indexes (a port of `gen_indexes.py`,
  byte-identical output, same non-zero exit on an unknown status), the
  sidebar nav from `zensical.toml`, and `routes.config.json`.
- Heading ids use Python-Markdown's slug rules, so `page.md#anchor` links
  keep working.
- `vite build` renders the pages with the plugin into `dist/`, with
  `minifyHtml: false`. Both options it relies on come from the unreleased
  [plugin PR #4](https://github.com/guilbep/vite-ssr-i18n-basic/pull/4),
  pinned as a GitHub tarball of its head commit.
- `Dockerfile` builds from the `docs/` context:
  `docker build -f docs/eta/Dockerfile docs/`.

## Measurements

About 380 source pages plus 4 generated indexes, Apple Silicon.

| Build                         | MkDocs | Zensical  | Vite + Eta |
| ----------------------------- | ------ | --------- | ---------- |
| Local, cold (no git plugins)  | 4.8 s  | 6.0–6.3 s | 0.7 s      |
| ↳ converter                   | n/a    | n/a       | 0.4 s      |
| ↳ `vite build`                | n/a    | n/a       | 0.3 s      |
| Local, cold, with HTML minify | n/a    | n/a       | 2.2 s      |
| Docker image, `--no-cache`    | 14.5 s | 14.2 s    | 6.1 s      |
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

No live reload for Markdown: `npm run dev` converts once at start, and
the plugin watches `src/pages/`, not `docs/src/`, so an edited page needs
a restart. Zensical's `serve` rebuilds on save. With the plugin's
directory check moved to build start, a small Vite plugin here could run
the converter and watch `docs/src/` (follow-up).

## Verification

- Same pages at the same paths as Zensical, minus `404.html`.
  `check_links.py dist`: 0 broken.
- Heading ids match Zensical on 358 of 386 pages. 27 differ only because
  Python-Markdown turns `#2487 text` (no space) into a heading and
  CommonMark does not; one archived plan gains a heading.
- A planted `status: draft` fails the converter.

## Plugin feedback

Filed as [guilbep/vite-ssr-i18n-basic#3](https://github.com/guilbep/vite-ssr-i18n-basic/issues/3);
fixed in [#4](https://github.com/guilbep/vite-ssr-i18n-basic/pull/4)
(unreleased): `emitRootRedirect` (off for one locale), `minifyHtml`,
render failures fail the build, directory check at build start, no
hardcoded `en`/`fr`, no debug logs. Still open: `sharp` (libvips CVEs,
build stage only, not in the image) and copying images next to pages,
which the converter does here.

## Decision

Open. Fastest of the three, but it trades features for speed. Adopting
it means a plugin release with #4, rebuilding search, highlighting, the
404 page and admonitions, and deleting `gen_indexes.py` for the port.
