---
status: delivered
issue: "3185"
last_updated: 2026-11-05
summary: Code Auditor follow-up. Drop the unused, unmaintained passlib (and its bcrypt and types-passlib baggage) from the backend, and bump certifi in the docs lock.
---

# 3185 — Code Auditor follow-up: drop passlib, refresh certifi

## What shipped

- `passlib[bcrypt]` and `types-passlib` removed from the backend with
  `uv remove`. Nothing imports them; passlib is unmaintained since 2020.
  The lock also drops `bcrypt` and picks up brotli 1.2.0 → 1.2.1.
- `docs/uv.lock`: certifi 2025.10.5 → 2026.10.23.
- Tech-stack page and a `ty.toml` comment no longer mention passlib.

## Audit on 2026-11-05

Same tools as `.github/workflows/security.yml`, run on this branch.

| Check                               | Result                               |
| ----------------------------------- | ------------------------------------ |
| npm audit root, frontend, storybook | 0 vulnerabilities                    |
| uv-audit --verbose backend, docs    | exit 0, no vulnerable package listed |
| bandit `app/`                       | no issues, only nosec warnings       |

Dependabot and code-scanning alerts were not readable with the agent's
token (HTTP 403). If the auditor flagged anything beyond this, it gets
its own follow-up under #3185.
