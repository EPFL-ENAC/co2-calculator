"""Pod heartbeat model — one row per live worker pod.

Backs the ``GET /v1/sync/workers`` endpoint and the
pipeline-operations console's "Workers" view (#1080 sprint-9
observability).  The motivating incident: a developer ran a local
branch against the stage DB while the deployed stage app was also
running.  Two pods on different code revisions both polled
``data_ingestion_jobs``, both held claims, and the surviving sibling
oracle stalled silently.  Logs alone gave no signal that two pods
were active; this table makes "who's claiming work right now" a
single SELECT.

Lifecycle:

* Each pod INSERTs (or UPDATEs on conflict) its row on startup.
* Heartbeat loop refreshes ``last_heartbeat_at`` every
  ``settings.POD_HEARTBEAT_INTERVAL_SECONDS`` (default 30s).
* On graceful shutdown the row is deleted; ungraceful shutdowns
  (pod-kill, OOM) leave it behind — the read endpoint filters by
  ``last_heartbeat_at > now() - 2x interval`` so dead pods drop out
  of the live list within ~1 minute.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import Column
from sqlalchemy import DateTime as SADateTime
from sqlmodel import Field, SQLModel


class Pod(SQLModel, table=True):
    """Live worker pod heartbeat.

    ``pod_id`` is the Kubernetes pod name (``$HOSTNAME``) — stable
    across heartbeats within a single pod's lifetime, unique across
    pods.  Falls back to ``socket.gethostname()`` for local dev.
    See ``app.tasks._pod_id``.
    """

    __tablename__ = "pods"

    pod_id: str = Field(primary_key=True, max_length=256)
    # Build provenance — set from ``GIT_SHA`` / ``APP_VERSION`` env at
    # startup.  Lets the workers view show "this pod is on commit X
    # vs this pod on commit Y" at a glance — the local-vs-stage
    # scenario that surfaced this requirement.
    git_sha: Optional[str] = Field(default=None, max_length=64)
    app_version: Optional[str] = Field(default=None, max_length=64)
    # When this pod first registered.  Differs from
    # ``last_heartbeat_at`` so the UI can show "pod uptime" alongside
    # "heartbeat age".  ``timezone=True`` so asyncpg / psycopg
    # round-trip tz-aware datetimes (the read endpoint's
    # ``now - last_heartbeat_at`` would otherwise raise
    # "can't subtract offset-naive and offset-aware datetimes").
    started_at: datetime = Field(
        sa_column=Column(SADateTime(timezone=True), nullable=False)
    )
    # Updated on every heartbeat tick.  The read endpoint uses this
    # to drop pods that haven't been seen recently.
    last_heartbeat_at: datetime = Field(
        sa_column=Column(SADateTime(timezone=True), nullable=False)
    )
