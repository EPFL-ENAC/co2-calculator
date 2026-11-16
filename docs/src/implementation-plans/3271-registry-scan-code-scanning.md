---
status: delivered
issue: "3271"
last_updated: 2026-11-16
summary: Registry scan findings become code scanning alerts (build-push-deploy-action v4.0.0), the docs image joins the scan, and dnspython moves to 2.9.2.
---

# 3271: registry scan to code scanning

## Problem

The weekly registry scan opened one 🚨 issue per vulnerable tag and digest.
Each `dev` or `stage` rebuild changed the digest and opened a new issue, and
no issue ever closed. #3271 (musl in `frontend:v1.4.21`) was already fixed
in code by the `GIT_SHA` cache-bust before `apk upgrade` (#3000), but its
issue stayed open.

## What shipped

- The scan logic moved to code scanning upstream, in
  [epfl-enac-build-push-deploy-action v4.0.0](https://github.com/EPFL-ENAC/epfl-enac-build-push-deploy-action/releases/tag/v4.0.0)
  (PR #35 there). Trivy SARIF is uploaded with one category per image and
  slot (`release`, `dev`, `stage`). If a later scan no longer reports a CVE,
  GitHub closes its alert.
- Each alert message names the workflow ref and commit, the Trivy version
  and DB date, the image digest, and the run.
- `image-vulnerability-scan.yml` pins v4.0.0 by SHA and grants
  `security-events: write` and `actions: read` instead of `issues: write`.
- The docs image joins the scanned images. It is built and deployed like the
  other two, but the scan did not cover it.
- The `deploy.yml` comment no longer says the scan runs before the push.
  The image is on ghcr under its sha tag before Trivy runs. The gate blocks
  the branch tag, the quay copy and the Argo update.
- dnspython 2.9.0 to 2.9.2 (GHSA-vvf4-9x63-8xvv), found by `make audit`.

## Verification

- A manual run from a test branch pinned to the PR head uploaded six
  analyses, and the alerts showed the tracing lines.
- Local `docker build --pull` of frontend, backend and docs, then
  `trivy image --severity HIGH,CRITICAL --exit-code 1`: all three exit 0.

## Where to look

Security > Code scanning, tool Trivy. Filter by category
`registry-scan/<image>:<slot>`. The old 🚨 issues were closed by hand.
