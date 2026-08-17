"""The simulator-plan prefill job handler (plan #2050 Track F4).

The plan PATCHes now persist only their metadata change and hand the copy
of a reference year into the plan years to this handler. These pin the
handler contract the runner depends on: registered under its job_type,
returns the meta dict, never writes the FINISHED state itself, and fails
loudly rather than silently doing nothing when its config is unusable.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.data_ingestion import DataIngestionJob
from app.tasks.registry import get_handler
from app.tasks.simulator_plan_tasks import simulator_plan_prefill_handler


def _job(config: dict | None, job_id: int | None = 7) -> DataIngestionJob:
    job = MagicMock(spec=DataIngestionJob)
    job.id = job_id
    job.meta = None if config is None else {"config": config}
    return job


@pytest.mark.asyncio
async def test_handler_is_registered_under_its_job_type():
    """The runner resolves handlers only through the registry."""
    from app.tasks.bootstrap import bootstrap_handlers

    bootstrap_handlers()
    assert get_handler("simulator_plan_prefill") is simulator_plan_prefill_handler


@pytest.mark.asyncio
async def test_handler_prefills_the_configured_reports():
    """Report ids from meta.config reach prefill_reports, on the data session."""
    data_session = MagicMock()
    with patch(
        "app.tasks.simulator_plan_tasks.SimulatorPlanService"
    ) as mock_service_cls:
        mock_service_cls.return_value.prefill_reports = AsyncMock(return_value=3)
        meta = await simulator_plan_prefill_handler(
            _job({"plan_id": 42, "report_ids": [10, 11, 12]}),
            MagicMock(),
            data_session,
        )
        mock_service_cls.assert_called_once_with(data_session)
        mock_service_cls.return_value.prefill_reports.assert_awaited_once_with(
            [10, 11, 12]
        )

    assert meta["result"] == {"plan_id": 42, "reports_prefilled": 3}
    # The runner persists this dict on its own FINISHED write — a handler
    # that set state itself would race it.
    assert "state" not in meta


@pytest.mark.asyncio
async def test_handler_raises_when_there_are_no_reports_to_prefill():
    """A job that would silently do nothing must fail instead.

    An empty report_ids list means the enqueuing route computed the wrong
    scope; finishing "successfully" would leave the plan year empty with
    no error anywhere (the no-silent-fallbacks rule).
    """
    with pytest.raises(ValueError, match="no report_ids"):
        await simulator_plan_prefill_handler(
            _job({"plan_id": 42, "report_ids": []}), MagicMock(), MagicMock()
        )


@pytest.mark.asyncio
async def test_handler_raises_on_missing_meta():
    """A job row with no meta at all is a bug, not an empty work list."""
    with pytest.raises(ValueError, match="no report_ids"):
        await simulator_plan_prefill_handler(_job(None), MagicMock(), MagicMock())
