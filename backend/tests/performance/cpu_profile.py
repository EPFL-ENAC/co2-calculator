"""CPU per request, per endpoint, in process (#2295).

The dev load ladder saturated on backend CPU (~30 ms per request on 1-core
pods) and Prometheus only gives a fleet mean. This drives ``app.main:app``
through ``httpx.ASGITransport``, one request at a time, so the
``time.process_time()`` delta around a request is that request's CPU, and
reports it next to wall time, SQL statements, pool checkouts and OTel spans
per request — for the ExplorerReadUser endpoints of ``locustfile.py``, with
the same parameters.

Run from ``backend/`` against the LOCAL compose Postgres, seeded
(``make perf-seed``; data-presence check in plan
2295-cpu-per-request-profile)::

    docker compose up -d otel      # repo root; or pass --exporter none
    uv run python -m tests.performance.cpu_profile                # off,prod,dev
    uv run python -m tests.performance.cpu_profile --levels sampling -n 200
    uv run python -m tests.performance.cpu_profile --levels prod -n 200
    uv run python -m tests.performance.cpu_profile --levels dev \
        --profile merged_report_stats
    uv run python -m tests.performance.cpu_profile --exporter none
    uv run python -m tests.performance.cpu_profile --log-level DEBUG

Levels are the pods' own OTEL_* env vars, so the numbers transfer:

- ``off``  — ``OTEL_SDK_DISABLED=true``. The instrumentation hooks still
  wrap the app (no-op spans), as when a pod flips that one variable.
- ``prod`` — chart default: ``sqlalchemy,psycopg`` disabled, ``always_on``.
- ``dev``  — ``always_on``, only ``sqlalchemy`` disabled: one psycopg span
  per SQL statement.
- ``dev0`` — as ``dev`` but ``always_off``: the instrumentation hooks run and
  nothing is recorded, the floor any head sampling can reach.
- ``prod10`` / ``prod1`` and ``dev10`` / ``dev1`` — as ``prod`` / ``dev`` with
  ``parentbased_traceidratio`` at 10 % / 1 %. Use ``-n 200`` or more at 1 %:
  a sampled request is rare, so small runs are noisy.

``--levels sampling`` runs the whole sweep in order: off, dev0, prod1,
prod10, prod, dev1, dev10, dev. Only head sampling (decided in the app at
span start) saves app CPU; tail sampling in the collector drops spans after
the app has created and exported them, so it saves nothing here.

``httpx`` instrumentation is disabled at every level: it would wrap this
harness's own client (the read path makes no httpx calls). Each level runs
in a child process started like the Dockerfile CMD, under
``opentelemetry-instrument``, with the instrumentations
``opentelemetry-bootstrap -a requirements`` lists (layered with
``uv run --with-requirements``; pyproject.toml is untouched). Child logs go
to ``reports/cpu_profile_<level>.log``, results to
``reports/cpu_profile_<level>.json``. ``--exporter otlp`` (default) sends
traces and metrics to the compose collector on localhost:4317, like the
pods; ``none`` creates spans and exports nothing.

``--profile <endpoint>`` runs a SEPARATE cProfile pass of n more requests
after the clean measurement, so profiler overhead never reaches the table.
It prints tottime by component and the top 25 functions, and dumps the
``.prof`` next to the JSON (``uv run python -m pstats <file>``).

The app lifespan is deliberately not run: its boot checks, ``init_db`` DDL
and background loops (poller, heartbeat, DB health, lag probe) are not on
the request path and their CPU would land in the per-request deltas.
"""

import argparse
import asyncio
import cProfile
import json
import os
import shutil
import socket
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
from opentelemetry import trace
from opentelemetry.sdk.trace import ReadableSpan, SpanProcessor, TracerProvider
from sqlalchemy import event
from sqlalchemy.engine import make_url

from app.core.config import get_settings
from app.core.security import SESSION_COOKIE
from app.db import engine
from app.main import app
from tests.performance.cpu_profile_stats import (
    ProfileEntry,
    Sample,
    component_breakdown,
    render_level,
    summarize_samples,
    top_functions,
)

MODULE = "tests.performance.cpu_profile"
BACKEND_DIR = Path(__file__).resolve().parents[2]
REPORTS = Path(__file__).resolve().parent / "reports"
LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})
COLLECTOR = ("localhost", 4317)
# Same knob as locustfile.MERGED_UNITS: unit ids per merged explorer query.
MERGED_UNITS = int(os.environ.get("PERF_MERGED_UNITS", "10"))
DB_SCOPES = (
    "opentelemetry.instrumentation.psycopg",
    "opentelemetry.instrumentation.sqlalchemy",
)

NO_SQL_SPANS = "httpx,sqlalchemy,psycopg"  # chart default: prod backend
PSYCOPG_SPANS = "httpx,sqlalchemy"  # dev and stage backends


def sampled(ratio: str, disabled: str) -> dict[str, str]:
    """Head sampling at a ratio, as a pod would set it."""
    return {
        "OTEL_TRACES_SAMPLER": "parentbased_traceidratio",
        "OTEL_TRACES_SAMPLER_ARG": ratio,
        "OTEL_PYTHON_DISABLED_INSTRUMENTATIONS": disabled,
    }


LEVELS: dict[str, dict[str, str]] = {
    "off": {
        "OTEL_SDK_DISABLED": "true",
        "OTEL_PYTHON_DISABLED_INSTRUMENTATIONS": NO_SQL_SPANS,
    },
    "dev0": {
        "OTEL_TRACES_SAMPLER": "always_off",
        "OTEL_PYTHON_DISABLED_INSTRUMENTATIONS": PSYCOPG_SPANS,
    },
    "prod1": sampled("0.01", NO_SQL_SPANS),
    "prod10": sampled("0.1", NO_SQL_SPANS),
    "prod": {
        "OTEL_TRACES_SAMPLER": "always_on",
        "OTEL_PYTHON_DISABLED_INSTRUMENTATIONS": NO_SQL_SPANS,
    },
    "dev1": sampled("0.01", PSYCOPG_SPANS),
    "dev10": sampled("0.1", PSYCOPG_SPANS),
    "dev": {
        "OTEL_TRACES_SAMPLER": "always_on",
        "OTEL_PYTHON_DISABLED_INSTRUMENTATIONS": PSYCOPG_SPANS,
    },
}
DEFAULT_LEVELS = ["off", "prod", "dev"]
# The whole sampling sweep, cheapest first; LEVELS is declared in this order.
SAMPLING_PRESET = "sampling"
# (any span, any per-statement DB span) each level must produce. At 1 % a
# default run still samples several of its ~900 requests.
EXPECTED_SPANS = {
    "off": (False, False),
    "dev0": (False, False),
    "prod1": (True, False),
    "prod10": (True, False),
    "prod": (True, False),
    "dev1": (True, True),
    "dev10": (True, True),
    "dev": (True, True),
}


@dataclass(frozen=True)
class Target:
    """The caller's units and years, cycled deterministically per request."""

    units: list[int]
    years: list[int]

    def unit(self, i: int) -> int:
        return self.units[i % len(self.units)]

    def year(self, i: int) -> int:
        return self.years[i % len(self.years)]

    @property
    def merged(self) -> list[int]:
        return self.units[:MERGED_UNITS]


Params = dict[str, int | list[int]]
Request = Callable[[Target, int], tuple[str, Params]]
_MERGED = "/v1/modules-stats/merged"

# ExplorerReadUser's tasks (same names), plus the session bootstrap every
# locust user starts with and healthz as the no-SQL floor.
ENDPOINTS: dict[str, Request] = {
    "healthz": lambda t, i: ("/healthz", {}),
    "session": lambda t, i: ("/v1/session", {}),
    "workspace_home": lambda t, i: (
        f"/v1/workspace/{t.unit(i)}/{t.year(i)}/home",
        {},
    ),
    "merged_report_stats": lambda t, i: (
        f"{_MERGED}/report-stats",
        {"unit_ids": t.merged, "year": t.year(i)},
    ),
    "merged_results_summary": lambda t, i: (
        f"{_MERGED}/results-summary",
        {"unit_ids": t.merged, "year": t.year(i)},
    ),
    "merged_multi_year": lambda t, i: (
        f"{_MERGED}/multi-year-report-stats",
        {"unit_ids": t.merged},
    ),
    "unit_totals": lambda t, i: (f"/v1/unit/{t.unit(i)}/{t.year(i)}/totals", {}),
    "unit_results": lambda t, i: (f"/v1/unit/{t.unit(i)}/results", {}),
    "explore_read": lambda t, i: (
        f"/v1/carbon-reports/simulator/explore/unit/{t.unit(i)}/",
        {},
    ),
}


class SpanCounter(SpanProcessor):
    """Counts ended spans; ``db`` = per-statement psycopg/sqlalchemy spans."""

    def __init__(self) -> None:
        self.total = 0
        self.db = 0

    def on_end(self, span: ReadableSpan) -> None:
        self.total += 1
        scope = span.instrumentation_scope
        if scope is not None and scope.name.startswith(DB_SCOPES):
            self.db += 1


class DbCounter:
    """SQLAlchemy statements and pool checkouts (each checkout pre-pings)."""

    def __init__(self) -> None:
        self.statements = 0
        self.checkouts = 0

    def on_statement(self, conn, cursor, statement, params, context, many) -> None:
        self.statements += 1

    def on_checkout(self, dbapi_connection, record, proxy) -> None:
        self.checkouts += 1


@dataclass(frozen=True)
class Probe:
    db: DbCounter
    spans: SpanCounter


def assert_local_db(db_url: str | None) -> str:
    """Refuse anything but a local Postgres; returns its host.

    Reads the resolved settings, whichever source won: a remote .env once
    dropped prod (docs/src/infra/07-postmortem-prod-db-dropped.md).
    """
    if db_url is None:
        raise RuntimeError("DB_URL is not set; the CPU profile needs local Postgres")
    url = make_url(db_url)
    backend, host = url.get_backend_name(), url.host
    if backend != "postgresql" or host not in LOCAL_HOSTS:
        raise RuntimeError(
            f"refusing to run: the resolved DB_URL is {backend} on host {host!r}. "
            f"The CPU profile only runs against a local Postgres "
            f"({', '.join(sorted(LOCAL_HOSTS))}); point backend/.env there."
        )
    return host


def attach_probe() -> Probe:
    """Hook the counters onto the app's engine and the global tracer."""
    provider = trace.get_tracer_provider()
    if not isinstance(provider, TracerProvider):
        raise RuntimeError(
            "no OTel SDK tracer provider: the worker must start under "
            "opentelemetry-instrument — run without --worker"
        )
    spans = SpanCounter()
    provider.add_span_processor(spans)
    db = DbCounter()
    event.listen(engine.sync_engine, "before_cursor_execute", db.on_statement)
    event.listen(engine.sync_engine.pool, "checkout", db.on_checkout)
    return Probe(db=db, spans=spans)


def require_status(response: httpx.Response, expected: int = 200) -> None:
    if response.status_code != expected:
        raise RuntimeError(
            f"{response.request.method} {response.request.url} -> "
            f"{response.status_code} (expected {expected}): {response.text[:500]}"
        )


async def login(client: httpx.AsyncClient, role: str) -> None:
    """The real auth path: one login-test, then its cookie on every request."""
    if not get_settings().DEBUG:
        raise RuntimeError(
            "GET /v1/auth/login-test only exists when DEBUG=true: set "
            "DEBUG=True in backend/.env (local only, never stage/prod)"
        )
    response = await client.get("/v1/auth/login-test", params={"role": role})
    require_status(response, 302)
    token = response.cookies.get(SESSION_COOKIE)
    if not token:
        raise RuntimeError(f"login-test set no {SESSION_COOKIE} cookie")
    # Set without the Secure flag so it is sent over the http base URL.
    client.cookies.clear()
    client.cookies.set(SESSION_COOKIE, token)


async def session_target(client: httpx.AsyncClient, role: str) -> Target:
    """Units and years from /v1/session, as CO2User.on_start does."""
    response = await client.get("/v1/session")
    require_status(response)
    body = response.json()
    units = [unit["id"] for unit in body["units"]]
    years = [year["year"] for year in body["configured_years"]]
    if not units or not years:
        raise RuntimeError(
            f"no units ({units}) or years ({years}) for role {role}: seed the "
            "backdrop first (make perf-seed), see plan 2295-cpu-per-request-profile"
        )
    return Target(units=units, years=years)


def verify_tracing(level: str, spans: SpanCounter) -> None:
    """Fail unless the spans seen so far match what the level promises."""
    seen = (spans.total > 0, spans.db > 0)
    if seen != EXPECTED_SPANS[level]:
        raise RuntimeError(
            f"level {level}: expected (spans, db spans) = {EXPECTED_SPANS[level]}, "
            f"saw {seen} ({spans.total} spans, {spans.db} db). The "
            "instrumentation does not match the level's env; check the log."
        )


async def ensure_explore_sandboxes(client: httpx.AsyncClient, units: list[int]) -> int:
    """explore_read 404s until a sandbox exists: POST one, as the SPA does."""
    created = 0
    for unit_id in units:
        path = f"/v1/carbon-reports/simulator/explore/unit/{unit_id}/"
        response = await client.get(path)
        if response.status_code != 404:
            require_status(response)
            continue
        require_status(await client.post(path), 201)
        created += 1
    return created


async def timed_get(
    client: httpx.AsyncClient, probe: Probe, path: str, params: Params
) -> Sample:
    statements, checkouts = probe.db.statements, probe.db.checkouts
    spans = probe.spans.total
    cpu, wall = time.process_time(), time.perf_counter()
    response = await client.get(path, params=params)
    wall, cpu = time.perf_counter() - wall, time.process_time() - cpu
    require_status(response)
    return Sample(
        cpu_ms=cpu * 1000,
        wall_ms=wall * 1000,
        statements=probe.db.statements - statements,
        checkouts=probe.db.checkouts - checkouts,
        spans=probe.spans.total - spans,
    )


async def drive(
    client: httpx.AsyncClient, probe: Probe, target: Target, request: Request, n: int
) -> list[Sample]:
    return [await timed_get(client, probe, *request(target, i)) for i in range(n)]


async def profile_endpoint(
    client: httpx.AsyncClient, probe: Probe, target: Target, args: argparse.Namespace
) -> dict[str, Any]:
    """Separate cProfile pass: the measured numbers stay profiler-free."""
    name, n = args.profile, args.requests
    dump = REPORTS / f"cpu_profile_{args.worker}_{name}.prof"
    profiler = cProfile.Profile()
    profiler.enable()
    await drive(client, probe, target, ENDPOINTS[name], n)
    profiler.disable()
    profiler.dump_stats(dump)  # also snapshots profiler.stats
    entries = [
        ProfileEntry(filename, lineno, funcname, ncalls, tottime, cumtime)
        for (filename, lineno, funcname), (_cc, ncalls, tottime, cumtime, _callers) in (
            profiler.stats.items()
        )
    ]
    return {
        "endpoint": name,
        "requests": n,
        "dump": str(dump.relative_to(BACKEND_DIR)),
        "components": component_breakdown(entries, n),
        "top": top_functions(entries, n),
    }


async def measure_level(args: argparse.Namespace) -> dict[str, Any]:
    probe = attach_probe()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://perf.local",
        # RequestOriginMiddleware's sanctioned marker for cookie-authed writes.
        headers={"Sec-Fetch-Site": "none"},
    ) as client:
        await login(client, args.role)
        target = await session_target(client, args.role)
        verify_tracing(args.worker, probe.spans)
        created = await ensure_explore_sandboxes(client, target.units)
        print(f"target {target}, explore sandboxes created: {created}", flush=True)
        endpoints: dict[str, dict[str, Any]] = {}
        for name, request in ENDPOINTS.items():
            await drive(client, probe, target, request, args.warmup)
            samples = await drive(client, probe, target, request, args.requests)
            endpoints[name] = summarize_samples(samples)
            print(f"{name}: {endpoints[name]}", flush=True)
        profile = None
        if args.profile:
            profile = await profile_endpoint(client, probe, target, args)
    await engine.dispose()
    return {"target": target, "endpoints": endpoints, "profile": profile}


def run_worker(args: argparse.Namespace, db_host: str) -> None:
    """One level, in this process (started by the orchestrator)."""
    settings = get_settings()
    # Env beats .env in Settings; prove the override landed.
    if settings.LOG_LEVEL.upper() != args.log_level.upper():
        raise RuntimeError(
            f"LOG_LEVEL resolved to {settings.LOG_LEVEL}, expected {args.log_level}"
        )
    result = asyncio.run(measure_level(args))
    target: Target = result["target"]
    report = {
        "level": args.worker,
        "otel_env": {k: v for k, v in os.environ.items() if k.startswith("OTEL_")},
        "log_level": settings.LOG_LEVEL,
        "db_host": db_host,
        "role": args.role,
        "units": target.units,
        "years": target.years,
        "merged_units": len(target.merged),
        "warmup": args.warmup,
        "requests": args.requests,
        "endpoints": result["endpoints"],
        "profile": result["profile"],
    }
    path = REPORTS / f"cpu_profile_{args.worker}.json"
    path.write_text(json.dumps(report, indent=2))


def require_collector() -> None:
    try:
        socket.create_connection(COLLECTOR, timeout=2).close()
    except OSError as exc:
        raise RuntimeError(
            f"no OTel collector on {COLLECTOR[0]}:{COLLECTOR[1]}: start it "
            "(docker compose up -d otel, repo root) or pass --exporter none"
        ) from exc


def write_otel_requirements() -> Path:
    """The Dockerfile's step: every instrumentation for installed libraries."""
    bootstrap = Path(sys.executable).parent / "opentelemetry-bootstrap"
    listed = subprocess.run(
        [str(bootstrap), "-a", "requirements"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.split()
    path = REPORTS / "otel_requirements.txt"
    path.write_text("\n".join(dict.fromkeys(listed)) + "\n")
    return path


def level_env(level: str, args: argparse.Namespace) -> dict[str, str]:
    """The pod-style env for one level; inherited OTEL_* vars are dropped."""
    inherited = {k: v for k, v in os.environ.items() if not k.startswith("OTEL_")}
    otel = {
        "OTEL_SERVICE_NAME": "cpu-profile",
        "OTEL_TRACES_EXPORTER": args.exporter,
        "OTEL_METRICS_EXPORTER": args.exporter,
        "OTEL_LOGS_EXPORTER": "none",
        "OTEL_PYTHON_LOGGING_AUTO_INSTRUMENTATION_ENABLED": "false",
        "OTEL_EXPORTER_OTLP_PROTOCOL": "grpc",
        "OTEL_EXPORTER_OTLP_ENDPOINT": f"http://{COLLECTOR[0]}:{COLLECTOR[1]}",
    }
    return {
        **inherited,
        **otel,
        **LEVELS[level],
        "LOG_LEVEL": args.log_level,
    }


def run_child(level: str, args: argparse.Namespace, requirements: Path) -> dict:
    uv = shutil.which("uv")
    if uv is None:
        raise RuntimeError("uv not found on PATH")
    command = [uv, "run", "--with-requirements", str(requirements)]
    command += ["opentelemetry-instrument", "python", "-m", MODULE]
    command += ["--worker", level, "-n", str(args.requests)]
    command += ["--warmup", str(args.warmup), "--role", args.role]
    command += ["--log-level", args.log_level]
    command += ["--profile", args.profile] if args.profile else []
    log_path = REPORTS / f"cpu_profile_{level}.log"
    json_path = REPORTS / f"cpu_profile_{level}.json"
    json_path.unlink(missing_ok=True)
    print(f"level {level}: running, log {log_path}", flush=True)
    with log_path.open("w") as log:
        exit_code = subprocess.run(
            command,
            cwd=BACKEND_DIR,
            env=level_env(level, args),
            stdout=log,
            stderr=subprocess.STDOUT,
            check=False,
        ).returncode
    if exit_code != 0:
        tail = "\n".join(log_path.read_text().splitlines()[-40:])
        raise RuntimeError(f"level {level} exited {exit_code}; log tail:\n{tail}")
    return json.loads(json_path.read_text())


def parse_levels(raw: str) -> list[str]:
    if raw.strip() == SAMPLING_PRESET:
        return list(LEVELS)
    levels = [level.strip() for level in raw.split(",") if level.strip()]
    unknown = [level for level in levels if level not in LEVELS]
    if unknown or not levels:
        raise argparse.ArgumentTypeError(
            f"levels must be {SAMPLING_PRESET!r} or a comma list of "
            f"{', '.join(LEVELS)}; got {raw!r}"
        )
    return levels


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--levels", type=parse_levels, default=DEFAULT_LEVELS)
    parser.add_argument("-n", "--requests", type=int, default=50)
    parser.add_argument("--warmup", type=int, default=50)
    parser.add_argument("--profile", choices=list(ENDPOINTS))
    parser.add_argument("--exporter", choices=("otlp", "none"), default="otlp")
    parser.add_argument("--log-level", default="INFO")
    parser.add_argument(
        "--role", default=os.environ.get("PERF_ROLE", "calco2.user.principal")
    )
    parser.add_argument("--worker", choices=list(LEVELS), help=argparse.SUPPRESS)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    db_host = assert_local_db(get_settings().DB_URL)
    REPORTS.mkdir(exist_ok=True)
    if args.worker:
        run_worker(args, db_host)
        return 0
    if args.exporter == "otlp" and set(args.levels) - {"off"}:
        require_collector()
    requirements = write_otel_requirements()
    for level in args.levels:
        print(render_level(run_child(level, args, requirements)), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
