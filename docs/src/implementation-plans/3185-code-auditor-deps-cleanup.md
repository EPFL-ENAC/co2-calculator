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

## OpenTelemetry instrumentation is now locked

The image used to run `opentelemetry-bootstrap | uv pip install` after
`uv sync --no-dev`, so production instrumentation bypassed `uv.lock` and
every audit. `opentelemetry-instrumentation-fastapi` sat in the dev group
while production boot imported it.

The 23 packages bootstrap listed are now main dependencies at 0.66b2, with
the OpenTelemetry family upgraded to 0.66b2 / 1.45.2, and the bootstrap step
is gone. `app/main.py` imports the instrumentor at the top of the file.

## Audit tool

`uvx uv-audit` crashes with an `AssertionError` once the instrumentation
packages are main dependencies, and its last release was in 2024. CI and
`make audit` now run uv's built-in `uv audit --frozen`, which also covers
dev dependencies and the docs lock. The command is experimental, so the CI
job pins uv.

## Audit on 2026-11-05

| Check                               | Result                                  |
| ----------------------------------- | --------------------------------------- |
| npm audit root, frontend, storybook | 0 vulnerabilities                       |
| uv audit --frozen, backend          | exit 0, no known vulnerabilities in 165 |
| uv audit --frozen, docs             | exit 0, no known vulnerabilities in 45  |
| bandit `app/`                       | no issues, only nosec warnings          |

Dependabot and code-scanning alerts were not readable with the agent's
token (HTTP 403), so individual alerts are unconfirmed.
