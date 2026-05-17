# Dev Release Runbook

Step-by-step operational runbook for the **lead developer** (or a
**temporary lead developer** standing in) to cut a release. This is the
copy-paste command sequence; for the _why_ — versioning rules,
environment model, release calendar, approvals — see
[Release Management](release-management.md).

> Use this when you are the person promoting `dev → stage → main` for a
> sprint-end release, a hotfix, or a rollback, and you want exact
> commands in order, not policy.

**Related documentation:**

- [Release Management](release-management.md) — policy: versioning, environment model, calendar, approvals
- [CI/CD Pipeline](06-cicd-pipeline.md) — pipeline & deployment architecture
- [CI/CD Workflows](cicd-workflows.md) — GitHub Actions details
- [Workflow Guide](workflow-guide.md) — daily developer workflow

## Prerequisites

<!-- TODO: access/tools the lead needs before starting -->
<!-- e.g. write access to dev/stage/main, gh CLI authenticated, argocd -->
<!-- access, who to notify, where to announce, code-freeze status -->

_TBD_

## Sprint-end release (v0.x.x)

The normal path: promote the current sprint from `dev` through `stage`
to `main`, where `release-please` cuts the version. Policy &
environment rules: [Release Management → Release Process](release-management.md#release-process).

### Step 1 — Pre-flight checks

<!-- TODO: green CI on dev, PM sign-off done, code freeze in effect -->

_TBD_

### Step 2 — Promote dev → stage

<!-- TODO: exact git commands; fast-forward stage to dev; how to verify -->

_TBD_

### Step 3 — Validate on stage

<!-- TODO: what to run/check; who validates; how long; abort criteria -->

_TBD_

### Step 4 — Promote stage → main (release-please)

<!-- TODO: open the stage→main PR, external code review, merge, -->
<!-- release-please PR, merge that, tag/deploy verification -->

_TBD_

### Step 5 — Post-release verification

<!-- TODO: health checks, logs, sprint board, known-issues note -->

_TBD_

## Hotfix release

Critical production bug that cannot wait for the normal train. Policy
& approvers: [Release Management → Emergency Hotfix Process](release-management.md#emergency-hotfix-process).

<!-- TODO: branch from main, minimal fix, fast-track review, deploy, -->
<!-- backport to dev and stage -->

_TBD_

## Rollback

When a release is bad and must be reverted. Background:
[CI/CD Pipeline → Rollback Mechanisms](06-cicd-pipeline.md#rollback-mechanisms).

<!-- TODO: application rollback (argocd / git tag), DB rollback -->
<!-- (alembic downgrade), order of operations, verification -->

_TBD_

## Troubleshooting

Common failures during a release and how to recover.

<!-- TODO: symptom → cause → recovery table; e.g. release-please PR -->
<!-- not created, stage deploy stuck, migration fails on deploy -->

_TBD_
