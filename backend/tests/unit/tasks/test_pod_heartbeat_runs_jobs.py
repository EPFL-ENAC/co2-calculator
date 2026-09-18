"""#2853 — the heartbeat row says whether the pod runs jobs.

The workers view filters on ``pods.runs_jobs``; if the heartbeat stopped
writing it, every pod would silently vanish from that view.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.pod import pod_runs_jobs
from app.tasks import _pod_heartbeat


@pytest.mark.parametrize(
    ("poller", "inline", "expected"),
    [
        (True, False, True),  # deployed worker
        (False, True, True),  # local dev: endpoints run their own jobs
        (False, False, False),  # deployed API pod behind the worker split
    ],
)
def test_pod_runs_jobs_from_the_two_dispatch_switches(poller, inline, expected):
    settings = MagicMock(RUN_BACKGROUND_POLLER=poller, DISPATCH_JOBS_INLINE=inline)
    assert pod_runs_jobs(settings) is expected


@pytest.mark.asyncio
async def test_heartbeat_upsert_writes_runs_jobs():
    session = AsyncMock()
    session_cm = MagicMock()
    session_cm.__aenter__ = AsyncMock(return_value=session)
    session_cm.__aexit__ = AsyncMock(return_value=False)
    settings = MagicMock(
        GIT_SHA="abc",
        APP_VERSION="1",
        RUN_BACKGROUND_POLLER=False,
        DISPATCH_JOBS_INLINE=False,
    )

    with (
        patch.object(_pod_heartbeat, "SessionLocal", return_value=session_cm),
        patch.object(_pod_heartbeat, "get_settings", return_value=settings),
    ):
        await _pod_heartbeat._upsert_pod_row(started_at=datetime.now(UTC))

    stmt, params = session.execute.await_args.args
    assert params["runs_jobs"] is False
    assert "runs_jobs = EXCLUDED.runs_jobs" in str(stmt)
