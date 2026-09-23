---
status: delivered
issue: "2909"
last_updated: 2026-09-23
summary: dev deploys from gitlab.epfl.ch through the EPFL-ENAC/build-push-deploy CI/CD component, started when GitHub Actions was billing-locked and kept as a live trial of the fallback; stage, ci-test and v* tags stay on deploy.yml so each ref has one pipeline writing the overlays.
---

# 2909 — Deploy dev from gitlab.epfl.ch

## Why

On 2026-09-22 GitHub stopped running Actions for the whole EPFL-ENAC org,
public repos included. The Argo repos' `update_manifest` workflow stopped
too, so a `repository_dispatch` would be accepted and deploy nothing.

Billing was fixed the same day. `dev` stays on GitLab anyway, so the
fallback keeps running for real instead of rotting until the next outage.

## What shipped

- **`.gitlab-ci.yml`** includes the component
  `gitlab.epfl.ch/EPFL-ENAC/build-push-deploy/deploy@0.3.0` with the same
  inputs as `deploy.yml`: three build contexts, the chart smoke renders,
  `GIT_SHA` and `APP_VERSION`.
- **`scripts/app-version.sh`** computes `APP_VERSION` for both pipelines,
  reading `GITHUB_*` or `CI_*`. One copy, so the two cannot drift.
- **`mirror-to-gitlab.yml`** pushes every `dev` change to GitLab (deploy key
  `GITLAB_DEPLOY_KEY`, pinned host key). GitLab CE cannot pull from GitHub,
  and a push nobody remembers is a silent fallback. Since 2026-09-23 it is a
  20-line caller of the reusable workflow in the action (`v3.10.0`).
- **Image reuse** (`reuse_unchanged_images`, `build_key_paths: package.json`,
  no per-deploy rescan), same `enac.build.key` formula and label as
  `deploy.yml`, so both paths recognise each other's images. Component
  `0.3.0`, 2026-09-23.
- **One pipeline per ref.** GitLab runs on `dev` only. `deploy.yml` drops
  `dev` and keeps `stage`, `ci-test/**` and `v*.*.*`. Two pipelines on the
  same ref would each commit a different digest to the same overlay.
- **The component** replaces `epfl-enac-build-push-deploy-action`:
  - build, push to ghcr, Trivy HIGH/CRITICAL, `crane copy` to quay (same digest)
  - chart `1.0.<CI_PIPELINE_ID>[-dev|-rc]`; pipeline ids are instance-wide
    and already above the GitHub run numbers, so versions keep increasing
  - overlay commits through GitHub's `createCommitOnBranch`, instead of a
    dispatch
  - skips an image or chart the overlay doesn't list, and fails if none of
    the images is in it
- **Runners:** the group VM runner (#4562) and `enack8s` (#5224),
  EPFL-ENAC/enack8s-app-config#361 and #362. Both are privileged for
  `docker:dind`. `enack8s` takes protected refs only.
- **Variables:** group `GHCR_USERNAME`, `GHCR_TOKEN` and `MANIFEST_TOKEN`;
  project `QUAY_USERNAME` and `QUAY_PASSWORD` (`svc1751+ghaction`).

## Verified

- Pipeline 426358 on `ci-test/gitlab-deploy`: all three images built on
  both runners, Trivy clean, same digests on ghcr and quay, chart
  `1.0.426358-dev` pushed.
- Overlay edits dry-run against the real dev overlays of both Argo repos:
  only digests and the chart version change. `docs` is skipped on enack8s,
  which doesn't deploy it.
- The manifest job's real script ran in Alpine against a stubbed GitHub API
  and produced one correct commit request per Argo repo.

- First real `dev` deploy, 2026-09-22: #2911 merged → mirror run green
  from GitHub's runners (gitlab.epfl.ch is reachable from the public
  internet) → GitLab pipeline 426465 green → overlay commits
  enack8s-app-config `91a66806` and openshift-app-config `19bcae08`
  through the shared script, chart `1.0.426465-dev`.

## Operating it

GitHub stays where PRs merge. `mirror-to-gitlab.yml` pushes `dev` to
gitlab.epfl.ch, which deploys it. If GitHub Actions is down, push by hand:

```sh
git fetch origin && git push gitlab origin/dev:dev
```

Chart versions on GitLab are `1.0.<pipeline id>-dev` (~426k), far above
GitHub's run numbers. Harmless while `dev` stays on GitLab; if it ever
moves back, GitHub's chart-reuse check would see the GitLab version as
"latest" and republish once per run.

- Reuse, 2026-09-23: pipeline 426659 rebuilt everything once (no labels
  yet); pipeline 426661 on the same commit reused all three images and the
  chart (build jobs 20–29 s) and left both overlays untouched.

## Not ported

The action's `private_key`, `lfs` and `submodules` inputs; co2 uses none of
them. Tracking: <https://gitlab.epfl.ch/EPFL-ENAC/build-push-deploy/-/work_items/1>.
