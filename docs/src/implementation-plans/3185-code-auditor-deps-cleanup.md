---
status: delivered
issue: "3185"
last_updated: 2026-11-05
summary: Code Auditor follow-up. Drop passlib and other forgotten dependencies, move the FastAPI OTel instrumentation to main deps, move the dev-only Faker seeders out of app/, and bump certifi in the docs lock.
---

# 3185 — Code Auditor follow-up: drop passlib, refresh certifi

## What shipped

- `passlib[bcrypt]` and `types-passlib` removed from the backend with
  `uv remove`. Nothing imports them; passlib is unmaintained since 2020.
  The lock also drops `bcrypt` and picks up brotli 1.2.0 → 1.2.1.
- `docs/uv.lock`: certifi 2025.10.5 → 2026.10.23.
- Tech-stack page and a `ty.toml` comment no longer mention passlib.
- Other forgotten dependencies removed: `pytest-mock` and
  `pytest-elasticsearch` (no test uses their fixtures) and the frontend's
  `unwrapped` (never imported).
- `opentelemetry-instrumentation-fastapi` moves from the dev group to the
  main dependencies, since `app/main.py` imports it at startup.
- The Faker seeders move from `app/seed/random_generator` to
  `scripts/random_generator`. They are dev and perf tooling, they import
  the dev-only `asyncpg`, and they no longer ship in the image.

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
