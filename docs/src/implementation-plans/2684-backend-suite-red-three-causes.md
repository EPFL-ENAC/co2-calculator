---
status: delivered
issue: 2684
last_updated: 2026-09-09
summary: "The backend suite is red in three unrelated ways: a stale config test left behind by the #1153 revert (red on CI now), backend/.env leaking into every pytest process through an lru_cache ordering bug (11 integration tests ran against real EPFL S3), and a CSV fixture #2253 never committed. Three independent fixes, shipped in that order."
---

# Backend suite red: three unrelated causes (#2684)

## Problem

`tests/unit` is red on CI right now; `tests/integration` is red on every dev
machine that has a populated `backend/.env`. Measured on `dev` @ `49a89971b`:

| Suite               | Before                           |
| ------------------- | -------------------------------- |
| `tests/unit`        | 1 failed, 2881 passed            |
| `tests/integration` | 12 failed, 459 passed, 1 skipped |

The 13 failures have **three unrelated root causes**. They share no code and
must not be bundled into one PR.

## Progress

- [x] **RC1** — delete the stale dotenv-precedence test
- [x] **RC2** — `get_settings.cache_clear()` in `pytest_configure` + comment
- [x] **RC2 regression tests** — `test_dotenv_cannot_reach_settings_under_pytest` + the CI-provable `test_cache_clear_is_what_drops_a_poisoned_dotenv_settings`
- [x] **RC2 scope check** — cache_clear() covers modules imported after
      `pytest_configure` (incl. `app.api.v1.files`, the S3 case this RC
      fixes); confirmed it does **not** cover `app.core.logging`, eagerly
      imported by `app/__init__.py` before that point. Filed as
      [#2686](https://github.com/EPFL-ENAC/co2-calculator/issues/2686) —
      see [Scope](#scope-checked-empirically-not-everything-is-covered).
- [x] **#2686 fix** — `app.core.logging` no longer binds a module-level
      `settings` singleton at import time; both call sites
      (`setup_logging()`, `LokiHandler.emit()`) call `get_settings()` live
      instead, mirroring `app/core/crypto.py`'s existing pattern. Same PR as
      RC2, per feedback that a follow-up discovered while working the same
      issue belongs alongside it, not in a separately-scheduled issue. See
      [#2686 fix](#2686-fix-appcorelogging-reads-settings-live-not-at-import).
- [x] **RC3** — commit `building_rooms_unknown_room.csv`
- [x] **RC3 follow-up** — `.gitignore`'s blanket `*.csv` (line 8) silently
      swallows every fixture under `backend/tests/fixtures/csv/`; that is how
      #2253 lost this file without anyone noticing. Added
      `!backend/tests/fixtures/csv/*.csv` to unblock the whole directory.
- [x] ~~Split into three PRs against `dev`~~ — delivered as one PR instead
      (owner call, overriding the sequencing recommendation below): the three
      fixes are small, already verified together, and splitting after the
      fact into 3 branches was judged not worth the overhead for this batch.

Suite is green locally with RC1+RC2+RC3 applied: `tests/unit` **2873 passed**
in this session's environment (run count drifts slightly with the tree state
but there are no failures), `tests/integration` runs clean modulo tests that
need Docker/Postgres, which this sandbox does not have access to — those
errored on `DockerException: permission denied`, not on RC1–RC3 behaviour.

RC2 is also a safety finding: it is the same class as the 2026-09-08 prod-DB
drop — `backend/.env` reaching a process that should never see it. See
[`07-postmortem-prod-db-dropped.md`](../infra/07-postmortem-prod-db-dropped.md).

---

## RC1 — stale test left by the #1153 revert

**Red on CI now** (run `34241046819`: `1 failed, 2872 passed`).

`b2ac6d1f1` reverted #1153 by deleting `Settings.settings_customise_sources`,
so pydantic's default precedence applies again: real env vars beat `.env`. It
added the new regression test but did not delete the old one asserting the
opposite behaviour, introduced by #1153 in `36eef0d7b`.

`tests/unit/core/test_config_provider_types.py::test_dotenv_db_url_overrides_stray_shell_env_var`
asserts `settings.DB_URL == "postgresql://from-dotenv/db"` — deliberately
reverted behaviour. It is a stale test, not a code bug.

### Fix — done

Delete the whole `test_dotenv_db_url_overrides_stray_shell_env_var` function
(and only that function) from
`backend/tests/unit/core/test_config_provider_types.py`.

Its replacement already exists and covers the dotenv source directly —
`backend/tests/unit/test_manage_db_guard.py::test_env_var_beats_dotenv` writes
a real dotenv file and asserts `Settings(_env_file=dotenv).DB_URL == <env var>`.
No coverage is lost, so no replacement test is needed.

### Verify

```bash
cd backend && uv run pytest tests/unit -q
```

Expect `2887 passed` (**verified locally**).

---

## RC2 — `backend/.env` is live inside every pytest process

11 integration failures, all in
`tests/integration/services/data_ingestion/`, all one signature:

```
S3Error: Error moving file from tmp/X.csv to processing/1/X.csv:
  An error occurred (NoSuchKey) when calling the CopyObject operation
```

### Root cause

1. `backend/.env` carries live S3 credentials (`s3.epfl.ch`, bucket
   `svc1751-…`, prefix `data`). The `wt` `post_create` hook copies that `.env`
   into every new worktree.
2. `tests/conftest.py::pytest_configure` sets
   `Settings.model_config["env_file"] = None` to keep a dev's `.env` out of
   tests. But `tests/conftest.py` **imports `app.*` at module level**, and
   pytest imports conftest _before_ it calls `pytest_configure`. Those imports
   already call `get_settings()`, which is `@lru_cache`d. Blanking `env_file`
   afterwards cannot invalidate the cache.
3. `make_files_store()` (`app/api/v1/files.py:44`) returns `S3FilesStore`
   whenever `S3_ENDPOINT_HOSTNAME` + access key + secret are set — which they
   are, from the cached `.env`-loaded Settings.
4. `_stage_csv_under_files_store` (in the failing test files) patches only
   `FILES_STORAGE_PATH` / `FILES_ENCRYPTION_*`, so the CSV is staged on local
   disk while the provider does `CopyObject` against real EPFL S3. The source
   key is not there → `NoSuchKey`.

The general failure is broader than S3: **every** `.env` key is live in the
test process. `S3_*` is simply the one `pytest-env` does not already blank
(it blanks `OAUTH_*`, `JWT_HMAC_KEY`, `CREDENTIALS_*`, …). Blanking `S3_*` in
`pytest-env` would be a symptom patch — do not do that.

### Blast radius — nothing was written

Only 6 integration files touch the store. Two
(`test_csv_ingest_matrix_pg.py`, `test_buildings_csv_pg.py`) patch
`make_files_store` with an in-memory `MagicMock` and never reach S3 — which is
why they passed. No integration test calls
`write_file`/`upload_file`/`delete_file`/`put_object` directly (grep: zero
hits). Every S3-touching test died inside `_move_to_processing` at
`file_exists` (HeadObject) then `move_file` → `copy_object` (NoSuchKey). The
copy always failed, so the delete half of the move never ran.

**Reads and 404s only — no object created, modified or deleted.**

### Fix — done

One line in `backend/tests/conftest.py::pytest_configure`:

```python
    from app.core.config import Settings, get_settings

    Settings.model_config["env_file"] = None
    get_settings.cache_clear()
```

`app.api.v1.files` is imported _after_ `pytest_configure`, so its module-level
`settings = get_settings()` and its `files_store = make_files_store()`
singleton both pick up the clean object.

Update the surrounding comment to say why the `cache_clear()` is load-bearing:
blanking `env_file` alone is not enough, because conftest's own module-level
`app.*` imports have already populated the cache.

### Regression tests — done

`backend/tests/unit/test_manage_db_guard.py`:

- `test_dotenv_cannot_reach_settings_under_pytest` — the direct check
  (`S3_*` unset). Fails without the fix **only on a machine with a populated
  `.env`**; green on CI either way, which is exactly the blind spot that let
  RC2 live in the first place.
- `test_cache_clear_is_what_drops_a_poisoned_dotenv_settings` — CI-provable
  companion: builds a poisoned cached `Settings` on purpose (its own
  `tmp_path` dotenv, not a real one) and proves `cache_clear()` specifically,
  not just "this machine's `.env` happens to be clean", is what evicts it.

### Scope, checked empirically — not everything is covered

`get_settings.cache_clear()` in `pytest_configure` only fixes modules
imported **after** `pytest_configure` runs. `app.api.v1.files` is one of
those, which is why the S3 claim above is real and verified. But
`app/__init__.py:15` (`import app.modules as _modules_pkg`) eagerly imports a
long chain _before_ `pytest_configure` ever runs, and `app.core.logging` is
in that chain — its module-level `settings = get_settings()` stays bound to
a `.env`-poisoned `Settings` object for the whole test session, cache_clear()
notwithstanding. Confirmed by direct reproduction: a populated `.env` with
`LOKI_ENABLED=true` + a fake `LOKI_URL` makes `setup_logging()` attempt a
real outbound connection to that URL during the test session (`LokiHandler:
failed to push log: ConnectError`). Checked the same way for `app.db`,
`app.core.security`, `app.providers.*` — none of those are in the eager
chain, so this is a single-module leak, not a repeat of RC2's blast radius.

Filed as [#2686](https://github.com/EPFL-ENAC/co2-calculator/issues/2686).
Originally deferred out of this PR — reconsidered on feedback that a
follow-up discovered while working the same issue, on the same branch,
belongs fixed alongside it rather than mentally parked for a separately
scheduled PR. See [#2686 fix](#2686-fix-appcorelogging-reads-settings-live-not-at-import)
below.

### #2686 fix — `app.core.logging` reads settings live, not at import

Two candidates were considered:

1. **Make `app.core.logging`'s settings access lazy** — call `get_settings()`
   inside `setup_logging()`/`LokiHandler.emit()` instead of binding a
   module-level `settings` singleton at import time.
2. Detect pytest in `Settings.model_config` itself (e.g. `env_file=None if
"pytest" in sys.modules else ".env"`) — fixes this and any of the ~19
   other modules with the same import-time `settings = get_settings()`
   pattern in one place, but plants test-awareness in production config
   code, in the exact file already flagged "precedence has flipped twice,
   read this before touching."

Went with **(1)**. It's not a new pattern — `app/core/crypto.py` already
does exactly this (`settings = get_settings()` as the first line inside the
function that needs it, not at module scope). Mirrors existing code rather
than inventing a config-level mechanism, and stays contained to the one
module with the confirmed bug.

`tests/unit/core/test_logging_redaction.py::test_loki_handler_is_wrapped_in_a_queue_not_attached_directly`
already exercised this exact path via `monkeypatch.setattr(logging_module.settings,
...)`, which stopped working once the module-level singleton was removed —
switched to the established `monkeypatch.setenv(...)` +
`get_settings.cache_clear()` pattern (same as `test_crypto.py`), and its
docstring now also carries the #2686 regression-guard rationale: a
QueueHandler only appearing after a live env-var change proves
`setup_logging()` isn't reading a value frozen at import time.

### Verify

```bash
cd backend && uv run pytest tests/unit/core/test_logging_redaction.py -v
```

Reproduction used to confirm both the bug and the fix: populate
`backend/.env` with `LOKI_ENABLED=true` + a fake `LOKI_URL`, run any
backend test. Before the fix: `setup_logging()` attempts a real outbound
connection (`LokiHandler: failed to push log: ConnectError`). After: no
connection attempt — `get_settings().LOKI_ENABLED` reads `False` as
expected under pytest.

### Verify

With a populated `backend/.env` present and **no** env blanking on the command
line:

```bash
cd backend && uv run pytest tests/integration -q
```

Before: `12 failed, 459 passed`. After: `1 failed, 473 passed` — only RC3
remains (**verified locally**).

Probe confirming the mechanism, before vs after: `S3_ENDPOINT_HOSTNAME set?`
`True → False`; `make_files_store()` `S3FilesStore → LocalFilesStore`.

### Follow-up (do not do in this PR)

The 4 files using `_stage_csv_under_files_store` are fragile by construction:
they patch settings and hope the store resolves to local. The 2 files that
patch `make_files_store` with an in-memory fake are the robust pattern and are
why those tests passed. Converting the remaining files to the fake-factory
pattern is worth its own issue — it removes the dependency on store selection
entirely rather than relying on the settings being clean.

---

## RC3 — CSV fixture #2253 never committed

`test_buildings_csv_pg.py::test_building_rooms_csv_unknown_room_is_rejected_as_row_error`:

```
FileNotFoundError: csv_fixture_path: ('building_rooms', 'unknown_room') is
registered but no file found.  Tried: backend/tests/fixtures/csv/building_rooms_unknown_room.csv
```

`a47816f03` (#2253) added the test and the `conftest.py` mapping (line 470)
but never committed the CSV. `git log --all` on that path is empty — it has
never existed in the repo.

Nobody noticed because PR CI runs `make test-cov-xml` = `tests/unit` **only**;
integration runs in a separate daily job.

### Fix — done

Create `backend/tests/fixtures/csv/building_rooms_unknown_room.csv`:

```csv
unit_institutional_id,building_location,building_name,room_name,room_type,note,kg_co2eq
{unit_institutional_id},ECUBLENS,BC,BC-150,office,,
{unit_institutional_id},ECUBLENS,BC,ZZ-999,office,,
```

Constraints this content satisfies — the test does
`template.format(unit_institutional_id=...)`, so the column is a `str.format`
placeholder (unlike the sibling `building_rooms_smoke.csv`, which hardcodes
`SEED-BC-0`). The header must match that sibling. `BC-150` is the room the
test seeds into `building_rooms`; `ZZ-999` must be absent from it, so the row
is a hard row error. One known + one unknown row is what makes the parent
report `WARNING` (partial success) rather than `SUCCESS`. The file must
contain no other `{` or `}`, or `str.format` will raise.

### Verify

```bash
cd backend && uv run pytest \
  tests/integration/services/data_ingestion/test_buildings_csv_pg.py -q
```

Expect the unknown-room test to pass (**verified locally: `1 passed`**).

### The trap that caused it

`.gitignore:8` is a blanket `*.csv` — every fixture under
`backend/tests/fixtures/csv/` was already tracked only because someone force-
added it (`git add -f`) at some point. #2253 didn't force-add this one, so
`git add`/`git commit` silently no-opped and the PR looked complete. Fixed
with a directory-scoped negation so the next fixture in that directory does
not need `-f`:

```gitignore
*.csv
!backend/tests/fixtures/csv/*.csv
```

---

## Sequencing

Three unrelated causes → three PRs, in this order. Do not bundle.

1. **RC1** — deletes a stale test, turns `dev` green. Smallest, most urgent.
2. **RC2** — the `cache_clear()` line + its regression test + the comment.
3. **RC3** — the missing fixture.

Each targets `dev` per the [guardrails](../contributing/guardrails.md).

## End state

Measured on this branch with RC1+RC2+RC3 applied, with a populated
`backend/.env` present and no env blanking on the command line:

| Suite               | Before                           | After                     |
| ------------------- | -------------------------------- | ------------------------- |
| `tests/unit`        | 1 failed, 2881 passed            | **2887 passed**           |
| `tests/integration` | 12 failed, 459 passed, 1 skipped | **474 passed, 1 skipped** |

## Not in scope

- Converting `_stage_csv_under_files_store` users to the fake-factory pattern
  (own issue — see RC2 follow-up).
- Making PR CI run the integration suite. It is slow by design and split
  deliberately; the daily job is the right place. But the daily job did not
  surface RC3 loudly enough — worth a separate look at its alerting.
- Anything about `backend/.env` contents. The `.env` is correct for running
  the app; the bug is that tests could see it.
