---
status: delivered
issue: 2997
last_updated: 2026-10-02
summary: 24 backend tests failed on dev — 23 integration tests still monkeypatched is_permitted on route modules that #2934 moved to check_permission, and one unit test asserted a WARNING that a leaked process-global shutdown flag demotes to INFO; tests repointed at app.core.security.is_permitted and the flag pinned, no production change
---

# 2997 — stale permission patches and a leaked shutdown flag

Found while verifying #2996: `uv run pytest tests` on `dev` (v1.4.19) had
24 failures. Production code was fine; the tests were stale.

## 23 integration tests — patching a symbol that no longer exists

#2942 (#2934, `d235e476d`, 2026-09-25, first in v1.4.19) replaced the
inlined `is_permitted` + 403 in `year_configuration.py` and `files.py` with
`check_permission`. That commit updated the unit tests (they patch
`check_permission` on the route module). Four integration files still
monkeypatched `app.api.v1.{year_configuration,files}.is_permitted` and died
with `AttributeError` in setup:

- `tests/integration/backoffice/test_module_activation.py`
- `tests/integration/data_ingestion/test_csv_upload_e2e.py`
- `tests/integration/v1/test_year_configuration_init.py`
- `tests/integration/v1/test_year_configuration_list.py`

**Fix:** patch `app.core.security.is_permitted`, which `check_permission`
resolves at call time. The fakes keep their boolean admin toggle, and the
real `check_permission` still raises the real 403 with the route's detail.
This is why the integration tests patch one level lower than the unit tests:
they need the denial path to be real. The routes have no other gate that
would see the fake. `data_sync` still imports `is_permitted` itself, and its
patch stays.

## 1 unit test — order-dependent

`tests/unit/tasks/test_background.py::test_fire_and_forget_inside_asyncio_run_is_cancelled`
passed alone and failed after any test that exits `TestClient(app)`. The
lifespan shutdown calls `cancel_background_tasks`, which latches the
module-global `_SHUTTING_DOWN = True` for the rest of the process. `_on_done`
then logs the cancellation at INFO ("cancelled at shutdown") instead of the
WARNING the test asserts. The flag came with the #2696 shutdown drain
(1.4.11 pre-release, #2768, 2026-09-14).

**Fix:** pin `_SHUTTING_DOWN = False` with `monkeypatch`, as the sibling
`test_cancel_background_tasks_cancels_and_waits` already does. The latch is
correct in production (a process shuts down once), so the production code
is unchanged.

## Verification

- The five files together: 24 failed before, 30 passed after.
- Full backend suite: 3640 passed, 1 skipped, 0 failed.
