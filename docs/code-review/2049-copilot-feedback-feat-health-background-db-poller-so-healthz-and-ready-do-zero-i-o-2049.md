# Bot Review TODOs: PR #2092

Source Branch: `perf/2049-async-db-health-poller`
---

## Raw Feedback

### Summary Feedback (github-advanced-security)

---

### Summary Feedback (copilot-pull-request-reviewer)

## Pull request overview

Adds an in-process background DB health poller to eliminate per-request database I/O from `/healthz` and `/ready`, improving probe reliability under DB pool saturation while keeping liveness semantics (`/healthz` always 200) and failing readiness closed when the cached DB verdict is missing or stale.

**Changes:**

- Introduces `app/tasks/_db_health.py` to periodically run a bounded `SELECT 1` and cache a verdict (`ok`/`slow`/`down`) plus latency/error.
- Wires the poller into `app.main` lifespan and rewrites `/healthz` and `/ready` to consume cached state (including stale/never-checked handling).
- Adds new settings fields and unit/integration tests covering classification, staleness, and probe behavior.

### Reviewed changes

Copilot reviewed 7 out of 7 changed files in this pull request and generated 3 comments.

<details>
<summary>Show a summary per file</summary>

| File                                                         | Description                                                                               |
| ------------------------------------------------------------ | ----------------------------------------------------------------------------------------- |
| docs/src/implementation-plans/2049-async-db-health-poller.md | New delivered plan documenting the poller design and probe contract.                      |
| backend/app/tasks/_db_health.py                              | Implements the background DB poll loop, cached state, and freshness checks.               |
| backend/app/main.py                                          | Starts the poller in lifespan and changes `/healthz` + `/ready` to use cached DB health.  |
| backend/app/core/config.py                                   | Adds settings controlling poller enablement, interval, and “slow” threshold.              |
| backend/tests/unit/tasks/test_db_health.py                   | Unit tests for classification, timeout bounding, staleness, and loop hygiene.             |
| backend/tests/integration/test_main.py                       | Integration tests validating `/healthz`/`/ready` behavior against cached-state scenarios. |
| backend/tests/conftest.py                                    | Disables the new poller by default in tests to avoid background side effects.             |

</details>

<details>
<summary>Suppressed comments (1)</summary>

**backend/app/tasks/\_db_health.py:117**

- db_health_check_loop() catches Exception for the initial tick; this also catches asyncio.CancelledError, which can prevent clean cancellation during shutdown (the task will log and keep running instead of stopping). CancelledError should propagate here the same way it does in the main loop.

```
    try:
        await _check_once(settings)
    except Exception:
```

</details>

---

💡 <a href="/EPFL-ENAC/co2-calculator/new/dev?filename=.github/skills/code-review/SKILL.md" class="Link--inTextBlock" target="_blank" rel="noopener noreferrer">Add a `code-review` agent skill</a> or configure MCP servers for context-aware, tailored reviews. <a href="https://docs.github.com/en/copilot/how-tos/use-copilot-agents/request-a-code-review/use-code-review#mcp-servers-and-agent-skills" class="Link--inTextBlock" target="_blank" rel="noopener noreferrer">Learn more in the docs.</a>
---

### Summary Feedback (copilot-pull-request-reviewer)

## Pull request overview

Copilot reviewed 7 out of 7 changed files in this pull request and generated no new comments.

<details>
<summary>Suppressed comments (4)</summary>

**docs/src/implementation-plans/2049-async-db-health-poller.md:43**

- The setting name `DB_HEALTH_CHECK_INTERVAL_SECONDS` is split across two lines inside backticks, which breaks the Markdown code span and makes the env var name hard to copy/paste.

```
- No helm changes: `RUN_DB_HEALTH_POLLER`, `DB_HEALTH_CHECK_INTERVAL_
SECONDS`, `DB_HEALTH_SLOW_THRESHOLD_MS` all default correctly in code,
```

**backend/app/tasks/\_db_health.py:95**

- `error = str(e)` can be empty for some exception types (notably timeouts), which makes the `/ready` failure log less actionable. Consider ensuring a non-empty error string.

```
    except Exception as e:
        latency_ms = (time.monotonic() - start) * 1000
        status = "down"
        error = str(e)
```

**backend/app/tasks/\_db_health.py:32**

- This comment references `main.py`'s `READY_DB_TIMEOUT_SECONDS`, but that constant was removed as part of this PR, so the precedent note is now misleading.

```
# Bare constant, not a Settings field — same precedent as main.py's
# READY_DB_TIMEOUT_SECONDS. Bounds each check so a saturated pool can't
# make an iteration hang; a timeout here surfaces as status "down", same
# as any other DB failure.
```

**backend/app/tasks/\_db_health.py:120**

- The initial-tick guard catches `Exception`, which can swallow `asyncio.CancelledError` (depending on Python version/behavior) and prevent clean task shutdown during startup. Cancellation should always propagate.

```
    try:
        await _check_once(settings)
    except Exception:
        logger.warning(
            "db health check initial tick failed unexpectedly", exc_info=True
        )
```

</details>

---

### File: `backend/tests/unit/tasks/test_db_health.py` (Line 49) — github-advanced-security[bot]

## CodeQL / Unnecessary lambda

This 'lambda' is just a simple wrapper around a callable object. Use that object directly.

[Show more details](https://github.com/EPFL-ENAC/co2-calculator/security/code-scanning/737)
---

### File: `backend/tests/unit/tasks/test_db_health.py` (Line 60) — github-advanced-security[bot]

## CodeQL / Unnecessary lambda

This 'lambda' is just a simple wrapper around a callable object. Use that object directly.

[Show more details](https://github.com/EPFL-ENAC/co2-calculator/security/code-scanning/738)
---

### File: `backend/app/tasks/_db_health.py` (Line 93) — Copilot

When the DB check times out, the raised TimeoutError often stringifies to an empty string, so the cached/logged error can be blank. Including the exception type (and message when present) makes readiness logs and debugging much more actionable.

This issue also appears on line 115 of the same file.
---

### File: `backend/app/main.py` (Line 153) — Copilot

The DB health poller task is started (app.state.db_health_task) but never cancelled/awaited during lifespan shutdown, unlike the other background tasks. This can leave a pending task during shutdown ("Task was destroyed but it is pending" warnings) and can delay clean shutdown.
---

### File: `docs/src/implementation-plans/2049-async-db-health-poller.md` (Line null) — Copilot

The inline code span for `DB_HEALTH_CHECK_INTERVAL_SECONDS` is broken across a newline (``DB_HEALTH_CHECK_INTERVAL_` then `SECONDS``), which makes the plan harder to read/search.

---

## Action Items

### Critical: logic, security, correctness

_None — the one correctness-shaped claim (initial-tick `except Exception` swallowing `CancelledError`, `_db_health.py` original lines ~117/120) is **wrong**: `asyncio.CancelledError` has subclassed `BaseException`, not `Exception`, since Python 3.8 (this project runs 3.14), so `except Exception:` never catches it — cancellation already propagates correctly. Dropped._

### Maintainability / refactoring

- [x] **`backend/app/tasks/_db_health.py`** (Copilot, 2 near-duplicate comments) — `error = str(e)` in `_check_once`'s except branch can be an empty string for exceptions that stringify to nothing (notably a bare `TimeoutError`, which `asyncio.timeout()` raises), making the `/ready` failure log less actionable. Fix: `error = str(e) or type(e).__name__`. **Fixed** in `86234e4b`.
- [x] **`backend/app/tasks/_db_health.py:29-32`** (Copilot) — the module comment cites `main.py`'s `READY_DB_TIMEOUT_SECONDS` as precedent, but this same PR deleted that constant, so the reference is dangling/misleading. Fix: reworded to note the constant was removed by this PR's own `/ready` rewrite rather than pointing at a symbol that no longer exists. **Fixed** in `86234e4b`.
- [x] **`backend/tests/unit/tasks/test_db_health.py:49,60`** (GHAS CodeQL, `py/unnecessary-lambda`) — `lambda: _Session()` at both `SessionLocal` monkeypatches is a pure wrapper around a zero-arg constructor call; the bot is correct that production code always calls `SessionLocal()` with no args, so the lambda adds nothing. Fix: `monkeypatch.setattr(_db_health, "SessionLocal", _Session)`. **Fixed** in `86234e4b`.
- [x] **`docs/src/implementation-plans/2049-async-db-health-poller.md`** (Copilot + GHAS, same finding twice) — the `DB_HEALTH_CHECK_INTERVAL_SECONDS` code span was broken across a markdown line wrap in the doc's first draft. **Already fixed**: a later commit (`docs(plan): note the worker readinessProbe addition`, `9f7950b3`) rewrote this bullet and reflowed it correctly (verified: the setting name is no longer split across the wrap).
- [x] **`backend/app/main.py:153`** (Copilot) — `app.state.db_health_task` was started in `lifespan()` but never cancelled/awaited on shutdown, unlike the three sibling background loops. **Already fixed**: caught independently during the earlier `/code-review` pass and landed in commit `fix(main): cancel db_health_task on shutdown`, before this bot-review pass ran.

---
