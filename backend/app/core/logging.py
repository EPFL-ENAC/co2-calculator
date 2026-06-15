"""Logging configuration for the application."""

import json
import logging
import re
import sys
from datetime import UTC, datetime
from typing import Any, Dict, Optional

import httpx

from app.core.config import get_settings

settings = get_settings()

# OAuth + token query params that uvicorn.access would otherwise log verbatim
# as part of the request URL. The OAuth `code` is single-use and already
# consumed by the time the log line is written, but logging it is still bad
# hygiene (logs get copied, exported, indexed). Defense-in-depth scrub.
_REDACT_QS_PARAMS = (
    "code",
    "state",
    "session_state",
    "id_token",
    "access_token",
    "refresh_token",
    "token",
)
_REDACT_QS_RE = re.compile(
    r"(?<=[?&])(" + "|".join(_REDACT_QS_PARAMS) + r")=[^&\s\"']+",
    re.IGNORECASE,
)


class _RedactSensitiveQueryStringFilter(logging.Filter):
    """Replace sensitive query-param values in URLs with ``<redacted>``.

    Installed on the ``uvicorn.access`` logger so the OAuth callback URL
    (``GET /api/v1/auth/callback?code=...&state=...``) never lands in
    structured access logs in cleartext. Affects ``record.msg`` and
    ``record.args``; downstream formatters see the scrubbed text.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            if record.args:
                record.args = tuple(
                    _REDACT_QS_RE.sub(r"\1=<redacted>", a) if isinstance(a, str) else a
                    for a in record.args
                )
            if isinstance(record.msg, str):
                record.msg = _REDACT_QS_RE.sub(r"\1=<redacted>", record.msg)
        except Exception:  # nosec B110
            # Logging filters MUST NOT raise (Python contract: a raising
            # filter would drop the log line entirely). The scrub is
            # best-effort; on any failure we let the original record
            # through unmodified rather than losing it.
            pass
        return True


class JsonFormatter(logging.Formatter):
    """Minimal JSON formatter that preserves extra fields."""

    # Standard LogRecord attributes we don't want to duplicate in 'extra'
    _reserved = {
        "name",
        "msg",
        "args",
        "levelname",
        "levelno",
        "pathname",
        "filename",
        "module",
        "exc_info",
        "exc_text",
        "stack_info",
        "lineno",
        "funcName",
        "created",
        "msecs",
        "relativeCreated",
        "thread",
        "threadName",
        "processName",
        "process",
    }

    def format(self, record: logging.LogRecord) -> str:
        log: Dict[str, Any] = {
            "timestamp": datetime.now(UTC),
            "level": record.levelname,
            "logger": record.name,
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "message": record.getMessage(),
        }

        # Capture extra fields passed via logger.*(..., extra={...})
        extras = {
            k: v
            for k, v in record.__dict__.items()
            if k not in self._reserved and not k.startswith("_")
        }
        if extras:
            log["extra"] = extras

        # Serialize exception info if present
        if record.exc_info:
            log["exc_info"] = self.formatException(record.exc_info)

        return json.dumps(log, default=str)


class LokiHandler(logging.Handler):
    """Synchronous Loki push API handler using httpx."""

    def __init__(
        self,
        loki_url: str,
        tenant_id: Optional[str] = None,
        default_labels: Optional[Dict[str, str]] = None,
        timeout: float = 2.0,
        level: int = logging.INFO,
    ):
        super().__init__(level=level)
        self.endpoint = f"{loki_url.rstrip('/')}/loki/api/v1/push"
        self.tenant_id = tenant_id
        self.default_labels = default_labels or {}
        self.timeout = timeout
        self._client = httpx.Client(timeout=timeout)

    def emit(self, record: logging.LogRecord) -> None:
        try:
            # Timestamp in nanoseconds, as string
            ts_ns = str(int(record.created * 1e9))  # aligns to record time
            line = self.format(record)  # leverage attached formatter (JSON)

            # Keep labels low-cardinality; add level (small set) and job/env
            labels = {
                "job": settings.LOKI_LABEL_JOB or settings.APP_NAME,
                "env": settings.LOKI_LABEL_ENV or ("dev" if settings.DEBUG else "prod"),
                "level": record.levelname.lower(),
                **self.default_labels,
            }

            payload = {
                "streams": [
                    {
                        "stream": labels,
                        "values": [[ts_ns, line]],
                    }
                ]
            }

            headers = {"Content-Type": "application/json"}
            if self.tenant_id:
                headers["X-Scope-OrgID"] = self.tenant_id

            # Fire-and-forget; swallow errors to avoid breaking app logging
            self._client.post(self.endpoint, json=payload, headers=headers)
        except Exception as e:
            # Never raise from logging; attempt to write diagnostic info to stderr
            try:
                sys.stderr.write(
                    f"LokiHandler: failed to push log: {type(e).__name__}: {str(e)}\n"
                )
            except Exception:  # nosec B110
                # If stderr itself fails, there's nothing more we can do
                # This is the one acceptable case for bare pass in logging handlers
                pass

    def close(self) -> None:
        try:
            self._client.close()
        finally:
            super().close()


def setup_logging() -> None:
    """Configure application logging with JSON output and optional Loki. Idempotent."""
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    # Reset handlers to avoid duplicates on reload
    for h in logging.root.handlers[:]:
        logging.root.removeHandler(h)

    json_handler = logging.StreamHandler(sys.stdout)
    json_handler.setLevel(log_level)
    json_handler.setFormatter(JsonFormatter())

    logging.basicConfig(level=log_level, handlers=[json_handler], force=True)

    # Tweak noisy libs
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    # httpcore/httpx emit per-request connect/TLS/header DEBUG lines (e.g. the
    # ECB FX calls during recalc); watchfiles spams file-change DEBUG in dev.
    # They drown out pipeline progress, so cap them at WARNING.
    for noisy in ("httpcore", "httpx", "watchfiles"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    # Let uvicorn loggers propagate so they use our formatter/handlers
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "uvicorn.asgi"):
        lg = logging.getLogger(name)
        lg.handlers = []
        lg.propagate = True

    # Scrub OAuth/token query params from access logs (see filter docstring).
    logging.getLogger("uvicorn.access").addFilter(_RedactSensitiveQueryStringFilter())

    # Optional: add Loki handler if enabled
    if settings.LOKI_ENABLED and settings.LOKI_URL:
        loki_handler = LokiHandler(
            loki_url=settings.LOKI_URL,
            tenant_id=settings.LOKI_TENANT_ID,
            default_labels={},  # you can add static labels here if desired
            timeout=settings.LOKI_TIMEOUT,
            level=log_level,
        )
        # Use the same JSON line format for Loki
        loki_handler.setFormatter(JsonFormatter())
        logging.getLogger().addHandler(loki_handler)

    logging.getLogger(__name__).info(
        "Logging configured",
        extra={
            "level": settings.LOG_LEVEL,
            "loki_enabled": settings.LOKI_ENABLED,
            "loki_url": bool(settings.LOKI_URL),
        },
    )


def _sanitize_for_log(value):
    """Sanitize user-controlled values for logging to prevent log injection."""
    # Convert to string and remove problematic newline/carriage return characters
    return str(value).replace("\n", "").replace("\r", "")


def _sanitize_extra(extra: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Recursively sanitize all values in the extra dictionary."""
    if extra is None:
        return None
    return {k: _sanitize_for_log(v) for k, v in extra.items()}


class SanitizingLoggerAdapter(logging.LoggerAdapter):
    """Logger adapter that automatically sanitizes extra parameters."""

    def process(self, msg, kwargs):
        """Process the logging call to sanitize extra parameters."""
        if "extra" in kwargs and kwargs["extra"]:
            kwargs["extra"] = _sanitize_extra(kwargs["extra"])
        return msg, kwargs


def get_logger(name: str) -> logging.LoggerAdapter:
    """Get a logger instance with automatic sanitization of extra parameters."""
    logger = logging.getLogger(name)
    return SanitizingLoggerAdapter(logger, {})
