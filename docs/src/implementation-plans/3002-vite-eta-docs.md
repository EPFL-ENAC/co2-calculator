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
- `vite build` renders the pages with the plugin into `dist/docs/`.
- `Dockerfile` builds from the `docs/` context:
  `docker build -f docs/eta/Dockerfile docs/`.

## Measurements

About 380 source pages plus 4 generated indexes, Apple Silicon.

| Build                            | MkDocs | Zensical  | Vite + Eta |
| -------------------------------- | ------ | --------- | ---------- |
| Local, cold (no git plugins)     | 4.8 s  | 6.0–6.3 s | 2.2 s      |
| ↳ converter                      | n/a    | n/a       | 0.4 s      |
| ↳ `vite build`                   | n/a    | n/a       | 1.8 s      |
| Local, cold, without HTML minify | n/a    | n/a       | 0.7 s      |
| Docker image, `--no-cache`       | 14.5 s | 14.2 s    | 8.8 s      |
| Image size                       | 74 MB  | 71 MB     | 44 MB      |
| Site size                        | 34 MB  | 33 MB     | 9.7 MB     |

1.5 s of the 1.8 s `vite build` is the plugin's `html-minifier-terser`,
run page by page. MkDocs and Zensical here do not minify.

Part of the gap is doing less work. This variant has no search index,
no 404 page, no per-page table of contents, no Material theme, no
admonitions, footnotes or `attr_list` (one page each), and no syntax
highlighting (Zensical runs Pygments on 197 pages).

No live reload for Markdown: `npm run dev` converts once at start, and
the plugin watches `src/pages/`, not `docs/src/`, so an edited page needs
a restart. Zensical's `serve` rebuilds on save.

## Verification

- Same pages at the same paths as Zensical, under `/docs/`, minus
  `404.html`. `check_links.py dist/docs`: 0 broken.
- Heading ids match Zensical on 358 of 386 pages. 27 differ only because
  Python-Markdown turns `#2487 text` (no space) into a heading and
  CommonMark does not; one archived plan gains a heading.
- A planted `status: draft` fails the converter.

## Plugin feedback (vite-ssr-i18n-basic 3.0.0)

- The root `index.html` language redirect is always written, so a
  single-locale site cannot have its home at `/`. Here pages sit under
  `/docs`. An `emitRootRedirect` option would fix it.
- Required directories are checked when `vite.config.js` loads, before
  any hook, so generated pages must exist before Vite starts.
- A page that fails to render logs `✗` and the build still exits 0.
- `html-minifier-terser` dominates build time (see above).
- Every build logs the asset manifest and the full page list.
- Only `src/assets/**` is processed; page images are copied by the
  converter.
- `npm audit`: high severity in `sharp` (libvips CVEs), pulled in as the
  plugin's optional dependency. Build stage only, not in the image.

## Decision

Open. Fastest of the three, but it trades features for speed. Adopting
it means rebuilding search, the 404 page and admonitions, deleting
`gen_indexes.py` for the port, and moving assets under `/docs`.
