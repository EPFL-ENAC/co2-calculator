"""Pure helpers of the CPU-per-request harness (#2295): statistics,
cProfile component bucketing, and the local-DB guard.
"""

import pytest

from tests.performance.cpu_profile import (
    DEFAULT_LEVELS,
    EXPECTED_SPANS,
    LEVELS,
    SAMPLING_PRESET,
    assert_local_db,
    checks_tracing_early,
    parse_levels,
)
from tests.performance.cpu_profile_stats import (
    APP,
    IO_WAIT,
    OTHER,
    ProfileEntry,
    Sample,
    component_breakdown,
    component_of,
    render_level,
    summarize,
    summarize_samples,
    top_functions,
)

LAPTOP = "/Users/dev/backend/.venv/lib/python3.14/site-packages"
# The prod image puts the venv under /app: must not read as app code.
IMAGE = "/app/.venv/lib/python3.14/site-packages"


def test_summarize_interpolates_p95():
    stats = summarize([float(v) for v in range(1, 21)])

    assert stats["mean"] == 10.5
    assert stats["median"] == 10.5
    assert stats["p95"] == pytest.approx(19.05)


def test_summarize_single_sample():
    assert summarize([5.0]) == {"mean": 5.0, "median": 5.0, "p95": 5.0}


def test_summarize_rejects_no_samples():
    with pytest.raises(ValueError, match="no samples"):
        summarize([])


def test_summarize_samples_cpu_per_statement():
    row = summarize_samples([Sample(8.0, 20.0, 4, 2, 5), Sample(12.0, 30.0, 6, 2, 7)])

    assert row["n"] == 2
    assert row["cpu_ms"]["mean"] == 10.0
    assert row["statements"] == 5.0
    assert row["checkouts"] == 2.0
    assert row["spans"] == 6.0
    assert row["cpu_ms_per_statement"] == 2.0


def test_summarize_samples_without_statements_has_no_per_statement_cpu():
    row = summarize_samples([Sample(1.0, 2.0, 0, 0, 1)])

    assert row["cpu_ms_per_statement"] is None


@pytest.mark.parametrize(
    ("filename", "funcname", "expected"),
    [
        (f"{LAPTOP}/sqlalchemy/orm/session.py", "execute", "sqlalchemy"),
        (f"{IMAGE}/sqlalchemy/orm/session.py", "execute", "sqlalchemy"),
        (f"{IMAGE}/sqlmodel/main.py", "exec", "sqlalchemy"),
        (f"{LAPTOP}/psycopg/cursor_async.py", "execute", "psycopg"),
        (f"{LAPTOP}/pydantic/main.py", "model_validate", "pydantic"),
        (
            "~",
            "<method 'validate_python' of "
            "'pydantic_core._pydantic_core.SchemaValidator' objects>",
            "pydantic",
        ),
        (f"{LAPTOP}/starlette/routing.py", "handle", "starlette/fastapi"),
        (f"{IMAGE}/fastapi/routing.py", "app", "starlette/fastapi"),
        (f"{LAPTOP}/opentelemetry/sdk/trace/__init__.py", "end", "opentelemetry"),
        (f"{LAPTOP}/wrapt/wrappers.py", "__call__", "opentelemetry"),
        (f"{LAPTOP}/httpx/_client.py", "send", "httpx (harness client)"),
        ("/Users/dev/backend/app/api/v1/unit_results.py", "get_totals", APP),
        ("/app/app/api/v1/unit_results.py", "get_totals", APP),
        ("/usr/local/lib/python3.14/asyncio/events.py", "_run", OTHER),
        ("<frozen importlib._bootstrap>", "_find_and_load", OTHER),
        ("~", "<method 'control' of 'select.kqueue' objects>", IO_WAIT),
        ("~", "<method 'poll' of 'select.epoll' objects>", IO_WAIT),
        ("~", "<built-in method builtins.isinstance>", OTHER),
        ("~", "<method 'append' of 'list' objects>", OTHER),
    ],
)
def test_component_of(filename, funcname, expected):
    assert component_of(filename, funcname) == expected


def _entry(filename: str, funcname: str, tottime: float) -> ProfileEntry:
    return ProfileEntry(filename, 1, funcname, 10, tottime, tottime)


def test_component_breakdown_keeps_io_wait_out_of_cpu_share():
    rows = component_breakdown(
        [
            _entry(f"{LAPTOP}/sqlalchemy/engine/base.py", "_execute", 0.02),
            _entry(f"{LAPTOP}/sqlalchemy/orm/loading.py", "instances", 0.01),
            _entry("/app/app/services/unit_service.py", "get_user_units", 0.01),
            _entry("~", "<method 'control' of 'select.kqueue' objects>", 0.5),
        ],
        requests=10,
    )

    by_component = {row["component"]: row for row in rows}
    assert by_component[IO_WAIT]["share"] is None
    assert by_component[IO_WAIT]["ms_per_request"] == pytest.approx(50.0)
    assert by_component["sqlalchemy"]["share"] == pytest.approx(0.75)
    assert by_component["sqlalchemy"]["ms_per_request"] == pytest.approx(3.0)
    assert by_component[APP]["share"] == pytest.approx(0.25)
    assert rows[0]["component"] == IO_WAIT


def test_component_breakdown_rejects_a_profile_without_cpu():
    with pytest.raises(ValueError, match="no CPU"):
        component_breakdown(
            [_entry("~", "<method 'control' of 'select.kqueue' objects>", 1.0)],
            requests=1,
        )


def test_top_functions_ranks_by_tottime_per_request():
    top = top_functions(
        [
            _entry(f"{LAPTOP}/pydantic/main.py", "model_validate", 0.01),
            _entry(f"{LAPTOP}/sqlalchemy/engine/base.py", "_execute", 0.04),
            _entry("/app/app/api/v1/unit_results.py", "get_totals", 0.02),
        ],
        requests=2,
        limit=2,
    )

    assert [row["function"] for row in top] == [
        "sqlalchemy/engine/base.py:1(_execute)",
        "app/api/v1/unit_results.py:1(get_totals)",
    ]
    assert top[0]["tottime_ms_per_request"] == pytest.approx(20.0)
    assert top[0]["calls_per_request"] == 5.0


def test_render_level_prints_one_row_per_endpoint():
    report = {
        "level": "prod",
        "otel_env": {"OTEL_TRACES_SAMPLER": "always_on"},
        "log_level": "INFO",
        "role": "calco2.user.principal",
        "units": [1, 2],
        "years": [2025],
        "merged_units": 2,
        "warmup": 1,
        "requests": 1,
        "endpoints": {"healthz": summarize_samples([Sample(1.0, 2.0, 0, 0, 1)])},
        "profile": None,
    }

    text = render_level(report)

    assert "### level `prod`" in text
    assert "`OTEL_TRACES_SAMPLER=always_on`" in text
    assert (
        "| healthz | 1 | 1.0 | 1.0 | 1.0 | 2.0 | 2.0 | 0.0 | 0.0 | 1.0 | n/a |" in text
    )


@pytest.mark.parametrize(
    "db_url",
    [
        "postgresql://localhost:5432/co2_calculator?sslmode=disable",
        "postgresql+psycopg://127.0.0.1/co2_calculator",
        "postgresql://[::1]:5432/co2_calculator",
    ],
)
def test_assert_local_db_accepts_local_postgres(db_url):
    assert assert_local_db(db_url) in {"localhost", "127.0.0.1", "::1"}


@pytest.mark.parametrize(
    "db_url",
    [
        "postgresql://co2-dev.example.org:5432/co2_calculator",
        "postgresql://postgres:5432/co2_calculator",
        "sqlite+aiosqlite:///./co2_calculator.db",
        None,
    ],
)
def test_assert_local_db_refuses_anything_else(db_url):
    with pytest.raises(RuntimeError):
        assert_local_db(db_url)


def test_every_level_declares_its_expected_spans():
    assert set(EXPECTED_SPANS) == set(LEVELS)


def test_ratio_levels_sample_a_fraction():
    ratios = {
        name: float(env["OTEL_TRACES_SAMPLER_ARG"])
        for name, env in LEVELS.items()
        if env.get("OTEL_TRACES_SAMPLER") == "parentbased_traceidratio"
    }
    assert ratios == {"prod1": 0.01, "prod10": 0.1, "dev1": 0.01, "dev10": 0.1}


def test_sampling_preset_runs_every_level_in_declared_order():
    assert parse_levels(SAMPLING_PRESET) == list(LEVELS)


def test_default_levels_are_unchanged():
    assert DEFAULT_LEVELS == ["off", "prod", "dev"]
    assert parse_levels("dev1, prod10") == ["dev1", "prod10"]


def test_ratio_levels_are_not_checked_before_any_endpoint_ran():
    # Regression: at 1 % the two bootstrap requests carry no span, so an early
    # check aborted every sampled level of --levels sampling (2026-09-25).
    assert not checks_tracing_early("prod1")
    assert not checks_tracing_early("dev10")
    assert checks_tracing_early("off")
    assert checks_tracing_early("dev")
