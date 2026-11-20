---
status: delivered
issue: 3333
last_updated: 2026-11-20
summary: "SECURITY.md states the CodeAuditor commitment. The docs move to Zensical. GitHub Pages deploys from the release's docs image."
---

# Zensical, security commitment and Pages from the release image

One branch, one PR. Three parts, in this order, because part 3 copies
the site that part 2 builds.

## 1. Security commitment

`SECURITY.md` at the repository root replaces the untouched GitHub
template. GitHub shows it in the Security tab. It states the rule once:

- CodeAuditor runs every week.
- A critical finding is fixed within 7 days. The target is 24 hours.

The older "Critical: fix within 24 hours" in `06-cicd-pipeline.md` and
the ADR-014 frequency list now link to `SECURITY.md`. Row 5 of the
security documentation index links to it. Reports go through GitHub
private vulnerability reporting, which is enabled.

## 2. MkDocs to Zensical

This is the approach of the closed PR #3003 (issue #3002). That PR
measured no build-time gain, and that still holds: about 5 s for both.
The reason to move now is that MkDocs 2.0 drops the plugin system, and
Zensical is the successor from the Material for MkDocs team. Zensical
runs no MkDocs plugins or hooks. Each one has a replacement:

| MkDocs piece                       | Replacement                                                                                                                         |
| ---------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| `mkdocs.yml`                       | `zensical.toml`, same nav, flat `.html` URLs, no `site_url`                                                                         |
| `gen-files` + `gen_indexes.py`     | `gen_indexes.py` runs before the build and writes gitignored `_index.md` files. An unknown plan status stops the build.             |
| `hooks.py` (repo-file links)       | A one-time rewrite of 87 links to `blob/HEAD` URLs. `check_links.py` (from the wiki) fails the build on any new dead relative link. |
| `--strict` link validation         | `zensical build --strict` fails on a missing page or anchor.                                                                        |
| git-authors, revision-date, minify | Dropped. The image build already skipped them, and nginx compresses the files.                                                      |
| `literate-nav`, PDF target         | Dropped. Neither was in use.                                                                                                        |

`docs/build.sh` is the one build definition. The Makefile, the
Dockerfile and the `Docs Build` CI job call it. The committed
`src/architecture.egg-info/` and the unused `requirements.txt` are
deleted.

## 3. GitHub Pages from the release image

`deploy-pages.yml` replaces `deploy-mkdocs.yml`. On a `vX.Y.Z` tag it
waits for `ghcr.io/epfl-enac/epfl/co2-calculator/docs:<tag>`, copies
`/usr/share/nginx/html` out of it, and publishes that to Pages. It uses
the exact tag, not `latest`, so Pages always matches the release that
triggered it. A manual run takes a tag to publish again.

Pull requests no longer build the docs in this workflow. The `Docs
Build` job of `quality-check.yml` does that on every pull request.

The image is public, so the workflow needs no registry login. Before
the first tag, add a tag rule `v*.*.*` to the `github-pages` environment.
It allows only `dev`, `gh-pages` and `main` today.
