"""Logging configuration for the application."""

import json
import logging
import sys
from datetime import datetime
from typing import Any, Dict, Optional

import httpx

from app.core.config import get_settings

settings = get_settings()


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
            "timestamp": datetime.utcnow().isoformat(timespec="milliseconds") + "Z",
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
        except Exception:
            # Never raise from logging; write a single line to stderr if needed
            try:
                sys.stderr.write("LokiHandler: failed to push log\n")
            except Exception:
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

    # Let uvicorn loggers propagate so they use our formatter/handlers
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "uvicorn.asgi"):
        lg = logging.getLogger(name)
        lg.handlers = []
        lg.propagate = True

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


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with the given name."""
    return logging.getLogger(name)
