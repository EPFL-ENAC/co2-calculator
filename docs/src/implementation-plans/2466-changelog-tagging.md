---
status: delivered
issue: 2466
last_updated: 2026-08-28
summary: "changelog.yml (dev -> stage) regenerates CHANGELOG.md via conventional-changelog, which always diffs from the latest git *tag*. Tags are only cut later, at the stage -> main promotion (release-please.yml), so every dev -> stage run before that tag exists re-diffed from the same stale tag and prepended a fresh overlapping block on top of whatever the previous untagged run already wrote (recurrence of #2352). Fixed by trimming CHANGELOG.md back to the last actually-tagged entry before each regenerate, instead of tagging earlier or dropping the dev -> stage step."
---

# CHANGELOG.md duplication on every dev -> stage merge (#2466)

## Symptom

`CHANGELOG.md`'s top block (`## [1.4.3](compare/v1.0.7...v1.4.3)`) and the
block right below it (`## [1.4.2](compare/v1.0.7...v1.4.2)`) both diffed from
`v1.0.7` — the last tag that actually exists. No `v1.4.0/1/2` tags were ever
cut, so two consecutive `dev -> stage` promotions each produced a full,
overlapping diff since `v1.0.7` instead of an incremental one.

## Root cause

- `changelog.yml` fires on every `dev -> stage` merge and runs
  `conventional-changelog -p angular -i CHANGELOG.md -s`, which always diffs
  from the latest existing **git tag** (via `git-semver-tags`).
- Tags are created only by `release-please.yml`, which fires later, on the
  `stage -> main` promotion.
- So every `dev -> stage` merge that happens before that `stage -> main`
  promotion regenerates against the same stale tag and **prepends** a new
  full diff — it never removes the previous untagged run's entry, because the
  tool has no notion of "this earlier block was never released."

## Options considered

**(a) Tag at `dev -> stage` too** (real version or a `-stage.N` suffix) so
conventional-changelog always has an immediately-preceding tag to diff from.
Rejected: `deploy.yml` triggers production image builds + ArgoCD updates on
`push: tags: ["v*.*.*"]`. That glob matches _any_ string starting with `v`
with two further `.`-separated segments — including `v1.4.4-stage.1` — so
every `dev -> stage` merge would additionally fire the prod-deploy path.
Making this safe means editing the production deploy trigger, which is an
infra/release-policy change, not a changelog fix.

**(b) Drop the `dev -> stage` changelog job entirely**, generate only at
`stage -> main`. Rejected on two counts:

- `release-please.yml` only _extracts_ the top `CHANGELOG.md` block for the
  GitHub Release body (`awk` between the first two `## [x.y.z]` headers) — it
  never generates one. Removing `changelog.yml` with no replacement leaves
  stage/main release notes stale.
- The release runbook (`docs/src/architecture/release-runbook.md`) documents
  an intentional human/LLM curation window on `stage`, between changelog
  generation and the `stage -> main` promotion. Moving generation to
  tag-time removes that window.
- A naive move (generate + commit CHANGELOG.md on `main`, _then_ tag) also
  risks the commit carrying `[skip ci]` in its message (needed to avoid
  re-triggering `deploy-storybook.yml`/`security.yml` on the `main` push) —
  and if the tag then points at that same commit, `[skip ci]` also suppresses
  `deploy.yml`'s tag-triggered **production deploy**, since GitHub's skip-ci
  check applies per commit, independent of which ref (branch or tag) is being
  pushed.

## Fix implemented

Neither (a) nor (b) is a clean changelog fix — both require touching the
production deploy trigger or the documented curation workflow, which is a
release-policy call, not a CI bug fix. The actual root cause is narrower:
`conventional-changelog` has no way to know a previous `CHANGELOG.md` entry
was never released, so it stacks a new diff instead of replacing it.

`.github/scripts/trim-unreleased-changelog.sh` walks `CHANGELOG.md`'s
`## [x.y.z]` headers top-down and drops every one whose `refs/tags/vX.Y.Z`
does not exist, stopping at the first that does. `changelog.yml` runs it
immediately before `conventional-changelog`. Result: each `dev -> stage` run
always starts from the last _actually released_ entry, so the regenerated
diff can never overlap a previous untagged run's content — it replaces it.

No tag policy, deploy trigger, or curation timing changed. Regression test:
`.github/scripts/trim-unreleased-changelog.test.sh` (synthetic repo with only
`v1.4.3` tagged, two untagged headers above it — asserts both are dropped and
`1.4.3`'s content survives).

`CHANGELOG.md`'s existing duplicate `## [1.4.2]` block (fully subsumed by the
`## [1.4.3]` block above it — same `v1.0.7` diff base, superset content) was
deleted by hand in the same commit; the script only prevents _future_
duplication, it doesn't retroactively clean history. Older, unrelated
oddities further down the file (duplicate `1.0.2` header, SHA-based compare
links for `1.1.1`/`1.0.8`) were left alone — pre-existing archaeology,
not part of this bug.
