# Post-mortem: production database dropped from a laptop

**Date:** 2026-09-08 · **Area:** Database / local tooling · **Severity:** prod
database emptied, no users yet (go-live 2026-09-22), restored from the 02:00
dump within the hour

## Summary

While `backend/.env` pointed at the prod DBaaS to run a read-only audit, an
AI coding session ran `tests/integration/test_alembic_migrations.py`. That
test drops and recreates a database through `scripts/manage_db.py` before
migrating it. It sets `DB_URL` to a local Docker container in the subprocess
environment, but this repo's settings let `.env` win over environment
variables, and `manage_db` defaults the database name to the one in that URL.
Prod received:

```sql
DROP DATABASE app WITH (FORCE);
CREATE DATABASE app;
-- then: alembic upgrade 6e32aa42f6f4
```

The same run happened once more against dev earlier that morning, which is
why dev looked empty. Stage was never targeted.

## Root cause

Three things lined up, none of them a bug on its own:

- `Settings.settings_customise_sources` puts `.env` before real environment
  variables, on purpose, so a stray `export DB_URL` cannot outrank a fixed
  `.env`. On a laptop this means every `get_settings()` call, including the
  one in `alembic/env.py` and `scripts/manage_db.py`, targets whatever `.env`
  says, whatever the caller exported.
- `manage_db` used `url.database` as the default name to drop or create, with
  no notion of "is this host mine to drop".
- The alembic smoke test drops and creates its target database with those
  two tools and ignores the drop's exit code, because a missing database is
  its normal starting state.

The trigger was operational: `.env` was pointed at a shared server for one
read-only command and stayed there while tests ran.

## Why it was hard to see

- The test's own output was green up to the seed step: `create` returned 0
  (on prod), `upgrade` returned 0 (on prod), then the seed failed with
  "database does not exist" on the local container. The failure looked like
  a Docker flake, so the test was rerun, three times.
- Nothing in the app logs: the app pods were idle, the drop came from a
  laptop with the app user's credentials.
- The DBaaS server showed no stray database afterwards, because the name
  dropped and recreated was the real one.

## Fix

Restored from the nightly dump on the `db-dumps` PVC using the restore pod
(`openshift-app-config/epfl/co2-calculator/tools/pod-db-restore.yaml`):
schema reset, `pg_restore --no-owner --no-privileges`, row counts checked
(257,871 entries, 18,944 factors, 511,385 emissions, revision
`095d98bc390c`). About nine hours of a database nobody was using were lost.

Guards, shipped in the same PR as the audit work (#2585):

- `scripts/manage_db.py` refuses to drop or create on a host that is not
  local unless `--allow-remote` is passed (`make db-drop ARGS=--allow-remote`).
- `tests/integration/test_alembic_migrations.py` ends the pytest session at
  import when the settings host is not local, instead of skipping.
- `tests/unit/test_manage_db_guard.py` pins the refusal.
- Settings precedence went back to pydantic's default, environment variables
  beat `.env` (#1153 reverted). A one-off `DB_URL=... uv run ...` now dies
  with the command instead of a file edit that retargets every tool in the
  repo. `test_alembic_migrations.py` refuses a non-local target of its own.

## Follow-up

- The restore procedure is now written down step by step, with a one-shot
  script piped into the restore pod:
  [`openshift-app-config` README, "Database dump and restore"](https://github.com/EPFL-ENAC/openshift-app-config/blob/main/epfl/co2-calculator/README.md#database-dump-and-restore)
  and [`tools/db-restore.sh`](https://github.com/EPFL-ENAC/openshift-app-config/blob/main/epfl/co2-calculator/tools/db-restore.sh)
  (PR openshift-app-config#39). The point-in-time path stays the
  `SI_POSTGRESQL` ticket in the [DRP](https://github.com/EPFL-ENAC/openshift-app-config/blob/main/epfl/co2-calculator/DRP.md#database-recovery).
- Dev can be restored the same way from its own PVC when someone needs it.
- Decide whether the nightly dump should run more often than 02:00 once real
  users arrive: the window between two dumps is the data at risk from
  anything the DBaaS point-in-time restore does not cover.

## Lessons

- **A read-only task does not make the session read-only.** Pointing `.env`
  at a shared server is a mode switch for every tool in the repo, not for
  the one command in mind. Switch it back the moment the command returns.
- **A test that drops databases must check whose database.** Ignoring the
  drop's exit code because "it might not exist yet" also ignores "it
  existed on the wrong server".
- **Green return codes are not evidence of the right target.** `create` and
  `upgrade` both returned 0; only the later "does not exist" on the
  intended host revealed where they had run. When a failure pattern-matches
  a flake, read the target before rerunning.
- **The dump was the whole recovery.** It existed because someone wired the
  CronJob and the PVC months earlier; keep it and keep testing the restore.
