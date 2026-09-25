"""Pure helpers for ``cpu_profile.py`` (#2295): summary statistics, cProfile
component bucketing and the markdown report. No I/O and no app imports, so
the unit tests load it without booting the app.
"""

import re
import statistics
from collections.abc import Iterable, Mapping
from typing import Any, NamedTuple

IO_WAIT = "io wait (not CPU)"
APP = "app"
OTHER = "other (stdlib, asyncio, logging, ...)"

# First match wins, keyed on the top-level package under site-packages (or
# a C method's owning module), so a prod-image path like
# /app/.venv/lib/.../site-packages/sqlalchemy/... never lands in APP.
COMPONENTS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("sqlalchemy", ("sqlalchemy", "sqlmodel")),
    ("psycopg", ("psycopg",)),
    ("pydantic", ("pydantic",)),
    # anyio: starlette's middleware and threadpool run on it.
    ("starlette/fastapi", ("starlette", "fastapi", "anyio")),
    # wrapt: only the OTel instrumentations wrap functions with it here.
    ("opentelemetry", ("opentelemetry", "wrapt")),
    ("httpx (harness client)", ("httpx", "httpcore")),
)

_SITE_PACKAGE = re.compile(r"site-packages/([^/]+)")
# cProfile labels C functions "<method 'x' of 'mod.Type' objects>" or
# "<built-in method mod.x>"; the owner's first dotted part is the module.
_C_OWNER = re.compile(r"of '([\w.]+)' objects|<built-in method ([\w.]+)>")
# The selector's blocking poll (select.kqueue/epoll/poll): wall-clock time
# the event loop spent waiting on Postgres, not CPU.
_IO_WAIT_MODULE = "select"

ENDPOINT_COLUMNS = (
    "endpoint",
    "n",
    "CPU ms mean",
    "CPU ms median",
    "CPU ms p95",
    "wall ms median",
    "wall ms p95",
    "SQL stmts/req",
    "pool checkouts/req",
    "spans/req",
    "CPU ms/stmt",
)

NOTES = (
    "CPU = `time.process_time()` delta around one request: the whole "
    "process, so it includes background threads (OTel batch span exporter, "
    "metric reader) and the in-process httpx client. `healthz` is the floor "
    "(middleware + harness, no auth, no SQL). SQL stmts = SQLAlchemy cursor "
    "executes. Every pool checkout also runs a pre-ping round trip that is "
    "not a statement here, so on `dev` spans/req can exceed stmts/req + 1."
)


class Sample(NamedTuple):
    """One measured request."""

    cpu_ms: float
    wall_ms: float
    statements: int
    checkouts: int
    spans: int


class ProfileEntry(NamedTuple):
    """One cProfile row (pstats key + its call count and times, seconds)."""

    filename: str
    lineno: int
    funcname: str
    ncalls: int
    tottime: float
    cumtime: float


def summarize(values: list[float]) -> dict[str, float]:
    """Mean, median and p95 (inclusive linear interpolation)."""
    if not values:
        raise ValueError("no samples to summarize")
    p95 = statistics.quantiles(values, n=20, method="inclusive")[-1]
    return {
        "mean": statistics.fmean(values),
        "median": statistics.median(values),
        "p95": p95,
    }


def summarize_samples(samples: list[Sample]) -> dict[str, Any]:
    """Per-endpoint row: CPU and wall stats plus per-request means."""
    cpu = summarize([s.cpu_ms for s in samples])
    wall = summarize([s.wall_ms for s in samples])
    statements = statistics.fmean(s.statements for s in samples)
    # A statement-free endpoint (healthz) has no CPU per statement.
    per_statement = cpu["mean"] / statements if statements else None
    return {
        "n": len(samples),
        "cpu_ms": cpu,
        "wall_ms": {"median": wall["median"], "p95": wall["p95"]},
        "statements": statements,
        "checkouts": statistics.fmean(s.checkouts for s in samples),
        "spans": statistics.fmean(s.spans for s in samples),
        "cpu_ms_per_statement": per_statement,
    }


def _package_component(package: str) -> str | None:
    for component, markers in COMPONENTS:
        if package.startswith(markers):
            return component
    return None


def component_of(filename: str, funcname: str) -> str:
    """Bucket one cProfile frame by the library that owns it."""
    if filename == "~":
        owner = _C_OWNER.search(funcname)
        module = next((g for g in owner.groups() if g), "") if owner else ""
        top = module.split(".")[0]
        if top == _IO_WAIT_MODULE:
            return IO_WAIT
        return _package_component(top) or OTHER
    path = filename.replace("\\", "/")
    package = _SITE_PACKAGE.search(path)
    if package:
        return _package_component(package.group(1)) or OTHER
    return APP if "/app/" in path else OTHER


def component_breakdown(
    entries: Iterable[ProfileEntry], requests: int
) -> list[dict[str, Any]]:
    """Tottime per component, per request, with its share of CPU.

    cProfile's default timer is wall clock, so time blocked in the selector
    is reported on its own row and left out of the share denominator.
    """
    totals: dict[str, float] = {}
    for entry in entries:
        component = component_of(entry.filename, entry.funcname)
        totals[component] = totals.get(component, 0.0) + entry.tottime
    cpu_total = sum(v for k, v in totals.items() if k != IO_WAIT)
    if cpu_total <= 0:
        raise ValueError("the profile recorded no CPU time")
    rows = [
        {
            "component": component,
            "ms_per_request": seconds * 1000 / requests,
            "share": None if component == IO_WAIT else seconds / cpu_total,
        }
        for component, seconds in totals.items()
    ]
    return sorted(rows, key=lambda row: -row["ms_per_request"])


def _short_path(filename: str) -> str:
    path = filename.replace("\\", "/")
    if "site-packages/" in path:
        return path.rsplit("site-packages/", 1)[1]
    if "/app/" in path:
        return "app/" + path.rsplit("/app/", 1)[1]
    return "/".join(path.split("/")[-3:])


def _label(entry: ProfileEntry) -> str:
    if entry.filename == "~":
        return entry.funcname
    return f"{_short_path(entry.filename)}:{entry.lineno}({entry.funcname})"


def top_functions(
    entries: Iterable[ProfileEntry], requests: int, limit: int = 25
) -> list[dict[str, Any]]:
    """The ``limit`` heaviest functions by tottime, per request."""
    ranked = sorted(entries, key=lambda e: -e.tottime)[:limit]
    return [
        {
            "function": _label(entry),
            "component": component_of(entry.filename, entry.funcname),
            "calls_per_request": entry.ncalls / requests,
            "tottime_ms_per_request": entry.tottime * 1000 / requests,
            "cumtime_ms_per_request": entry.cumtime * 1000 / requests,
        }
        for entry in ranked
    ]


def _table(header: Iterable[str], rows: Iterable[Iterable[str]]) -> str:
    header = list(header)
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    lines += ["| " + " | ".join(row) + " |" for row in rows]
    return "\n".join(lines)


def _fmt(value: float | None, digits: int = 1) -> str:
    return "n/a" if value is None else f"{value:.{digits}f}"


def _share(share: float | None) -> str:
    return "n/a" if share is None else f"{share:.0%}"


def _endpoint_row(name: str, row: Mapping[str, Any]) -> list[str]:
    cpu, wall = row["cpu_ms"], row["wall_ms"]
    return [
        name,
        str(row["n"]),
        _fmt(cpu["mean"]),
        _fmt(cpu["median"]),
        _fmt(cpu["p95"]),
        _fmt(wall["median"]),
        _fmt(wall["p95"]),
        _fmt(row["statements"]),
        _fmt(row["checkouts"]),
        _fmt(row["spans"]),
        _fmt(row["cpu_ms_per_statement"], 2),
    ]


def _profile_section(profile: Mapping[str, Any]) -> str:
    components = _table(
        ("component", "ms/request", "share of CPU"),
        (
            [r["component"], _fmt(r["ms_per_request"], 2), _share(r["share"])]
            for r in profile["components"]
        ),
    )
    top = _table(
        ("function", "component", "calls/req", "tottime ms/req", "cumtime ms/req"),
        (
            [
                f"`{r['function']}`",
                r["component"],
                _fmt(r["calls_per_request"]),
                _fmt(r["tottime_ms_per_request"], 3),
                _fmt(r["cumtime_ms_per_request"], 3),
            ]
            for r in profile["top"]
        ),
    )
    title = (
        f"#### cProfile `{profile['endpoint']}`: {profile['requests']} requests, "
        f"event-loop thread, wall-clock timer (`{profile['dump']}`)"
    )
    return f"{title}\n\n{components}\n\nTop {len(profile['top'])} by tottime:\n\n{top}"


def render_level(report: Mapping[str, Any]) -> str:
    """Markdown for one level's JSON report."""
    env = ", ".join(f"`{k}={v}`" for k, v in sorted(report["otel_env"].items()))
    title = f"### level `{report['level']}`"
    context = (
        f"role `{report['role']}`, {len(report['units'])} units, "
        f"{report['merged_units']} merged, years {report['years']}, "
        f"LOG_LEVEL {report['log_level']}, {report['warmup']} warm-up + "
        f"{report['requests']} measured per endpoint\n\n{env}"
    )
    table = _table(
        ENDPOINT_COLUMNS,
        (_endpoint_row(name, row) for name, row in report["endpoints"].items()),
    )
    parts = [title, context, table, NOTES]
    if report["profile"] is not None:
        parts.append(_profile_section(report["profile"]))
    return "\n\n".join(parts) + "\n"
