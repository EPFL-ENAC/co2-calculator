---
status: in-progress
issue: "2909"
last_updated: 2026-09-22
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
  `gitlab.epfl.ch/EPFL-ENAC/build-push-deploy/deploy@0.1.2` with the same
  inputs as `deploy.yml`: three build contexts, the chart smoke renders,
  `GIT_SHA`, and the `APP_VERSION` script. The script reads `package.json`
  with `jq` and uses `CI_*` variables.
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

Still to prove: the first real `dev` pipeline, which is the first time the
GitHub API sees `MANIFEST_TOKEN`. Flip `status` to `delivered` once it is
green and Argo has rolled out.

## Operating it

GitHub stays where PRs merge, and gitlab.epfl.ch has no pull mirror (CE). A
`dev` merge deploys once it's pushed there:

```sh
git fetch origin && git push gitlab origin/dev:dev
```

## Not ported

`reuse_unchanged_images`: every dev push rebuilds all three images, about
1–2 min each on a warm cache.
