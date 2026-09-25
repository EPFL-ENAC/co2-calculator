"""Tests for the probe access-log filter (#2934).

Liveness/readiness probes were 97% of the prod backend access log and 100%
of the worker's. A 200 probe line carries no information, so
``_DropHealthyProbeAccessLogFilter`` drops it on ``uvicorn.access``. A
non-200 probe answer and every real request must still log.
"""

import logging

import pytest

from app.core.logging import _DropHealthyProbeAccessLogFilter, setup_logging

UVICORN_ACCESS_MSG = '%s - "%s %s HTTP/%s" %d'


def _access_record(method: str, path: str, status: int) -> logging.LogRecord:
    return logging.LogRecord(
        name="uvicorn.access",
        level=logging.INFO,
        pathname=__file__,
        lineno=0,
        msg=UVICORN_ACCESS_MSG,
        args=("10.0.0.1:1234", method, path, "1.1", status),
        exc_info=None,
    )


@pytest.mark.parametrize("path", ["/healthz", "/ready"])
def test_healthy_probe_line_is_dropped(path: str):
    assert (
        _DropHealthyProbeAccessLogFilter().filter(_access_record("GET", path, 200))
        is False
    )


@pytest.mark.parametrize(
    ("path", "status"),
    [("/ready", 503), ("/healthz", 500), ("/v1/session", 200), ("/v1/session", 401)],
)
def test_failing_probe_and_real_requests_still_log(path: str, status: int):
    assert (
        _DropHealthyProbeAccessLogFilter().filter(_access_record("GET", path, status))
        is True
    )


def test_non_access_shaped_record_passes_through():
    record = logging.LogRecord(
        "uvicorn.access", logging.INFO, __file__, 0, "plain", (), None
    )
    assert _DropHealthyProbeAccessLogFilter().filter(record) is True


def test_setup_logging_installs_probe_filter_on_uvicorn_access():
    setup_logging()
    assert any(
        isinstance(f, _DropHealthyProbeAccessLogFilter)
        for f in logging.getLogger("uvicorn.access").filters
    )
