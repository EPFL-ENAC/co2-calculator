"""Tests for the access-log query-string redaction filter.

Regression guard for the issue surfaced during PR #1314 manual Safari
testing: uvicorn.access logs the full request URL including OAuth
``?code=...&state=...&session_state=...`` query params. The codes are
single-use but logging them is bad hygiene and a potential exfiltration
vector. ``_RedactSensitiveQueryStringFilter`` is the defense-in-depth
scrub installed on the ``uvicorn.access`` logger.
"""

import logging
import logging.handlers

from app.core import logging as logging_module
from app.core.logging import _RedactSensitiveQueryStringFilter, setup_logging


def _make_record(msg: str, args: tuple = ()) -> logging.LogRecord:
    return logging.LogRecord(
        name="uvicorn.access",
        level=logging.INFO,
        pathname=__file__,
        lineno=0,
        msg=msg,
        args=args,
        exc_info=None,
    )


def test_redact_oauth_code_in_message():
    """Single ``?code=...`` value is replaced with ``<redacted>``."""
    f = _RedactSensitiveQueryStringFilter()
    record = _make_record("GET /api/v1/auth/callback?code=SECRET_VALUE_HERE")
    assert f.filter(record) is True
    assert "SECRET_VALUE_HERE" not in record.msg
    assert "code=<redacted>" in record.msg


def test_redact_oauth_callback_full_querystring():
    """All sensitive params in a realistic OAuth callback URL are scrubbed."""
    f = _RedactSensitiveQueryStringFilter()
    record = _make_record(
        "GET /api/v1/auth/callback?code=ABC.123&state=NFBVP2bZ&session_state=00b79819"
    )
    assert f.filter(record) is True
    assert "ABC.123" not in record.msg
    assert "NFBVP2bZ" not in record.msg
    assert "00b79819" not in record.msg
    assert "code=<redacted>" in record.msg
    assert "state=<redacted>" in record.msg
    assert "session_state=<redacted>" in record.msg


def test_redact_in_args_tuple():
    """Uvicorn formats access logs via record.args; scrubber covers both."""
    f = _RedactSensitiveQueryStringFilter()
    record = _make_record(
        '%s - "%s" %d',
        args=("127.0.0.1", "GET /v1/auth/callback?code=SECRET HTTP/1.1", 302),
    )
    assert f.filter(record) is True
    assert "SECRET" not in str(record.args)
    assert "code=<redacted>" in str(record.args)


def test_redact_preserves_non_sensitive_params():
    """A benign ``?foo=bar`` query param must pass through untouched."""
    f = _RedactSensitiveQueryStringFilter()
    record = _make_record("GET /api/v1/units?foo=bar&year=2024")
    assert f.filter(record) is True
    assert "foo=bar" in record.msg
    assert "year=2024" in record.msg


def test_redact_filter_never_raises():
    """If args contain something un-string-able, filter must return True
    rather than dropping the log line.
    """
    f = _RedactSensitiveQueryStringFilter()
    record = _make_record("normal message", args=(object(), 1, None))
    assert f.filter(record) is True
    # Args may or may not be modified; the contract is "don't raise".


def test_setup_logging_installs_redactor_on_uvicorn_access():
    """The filter is useless if it isn't attached to the right logger.

    Regression guard against the wiring being silently dropped during a
    future refactor of `setup_logging`. Calls setup_logging() and asserts
    the uvicorn.access logger ends up with a
    _RedactSensitiveQueryStringFilter in its filter list.
    """
    setup_logging()

    access_logger = logging.getLogger("uvicorn.access")
    assert any(
        isinstance(f, _RedactSensitiveQueryStringFilter) for f in access_logger.filters
    ), (
        "uvicorn.access should have _RedactSensitiveQueryStringFilter "
        "installed; otherwise OAuth callback URLs land in logs verbatim."
    )


def test_loki_handler_is_wrapped_in_a_queue_not_attached_directly(monkeypatch):
    """#2050 Track I3 regression: LokiHandler.emit() does a blocking httpx
    POST. Attached straight to the root logger, every logger.info()+ call
    anywhere in the app would block the event loop for up to `timeout`
    seconds under Loki degradation. The fix must be a QueueHandler on the
    root logger — QueueHandler.emit() only ever enqueues, so this is a
    structural (not timing-based) proof the blocking call can't happen
    inline, regardless of how slow Loki is when the listener thread runs.
    """
    monkeypatch.setattr(logging_module.settings, "LOKI_ENABLED", True)
    monkeypatch.setattr(logging_module.settings, "LOKI_URL", "http://loki.example:3100")

    try:
        setup_logging()

        root_handlers = logging.getLogger().handlers
        queue_handlers = [
            h for h in root_handlers if isinstance(h, logging.handlers.QueueHandler)
        ]
        assert queue_handlers, (
            "Loki must be reached via a QueueHandler, not a bare LokiHandler "
            "on the root logger — a direct attachment blocks every log call."
        )
        assert not any(
            isinstance(h, logging_module.LokiHandler) for h in root_handlers
        ), "LokiHandler must live behind the queue, not on the root logger directly."
    finally:
        # Tear down: drop the QueueHandler so it doesn't leak into other
        # tests' log output. The listener thread it started is registered
        # via atexit and cleans up at interpreter shutdown — acceptable for
        # a config-time handler that's expected to live for process
        # lifetime in production too.
        for h in logging.getLogger().handlers[:]:
            if isinstance(h, logging.handlers.QueueHandler):
                logging.getLogger().removeHandler(h)
