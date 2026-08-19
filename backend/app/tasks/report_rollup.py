"""Detached report-stats rollup (#2050 J4).

A report's stats scan every module in the report, so the work grows with the
report rather than with the entry a user just created — and nothing the caller
reads back depends on it. Interactive writes therefore hand it here, to run
after the response on a session of its own.

No ``DataIngestionJob`` row: that would add an INSERT to the request to save
four statements, and would need its own coalescing story. Report stats are
derived and recomputable at any time, and the admin ``recompute-stats``
backfill already exists, so a lost rollup is staleness rather than data loss.
Failures surface through ``fire_and_forget``'s done-callback rather than being
swallowed.

Background callers (the aggregation job, plan prefill, recalc) keep rolling up
inline: they have nobody waiting, so in-transaction is the right place for them.
"""

from app.core.logging import get_logger
from app.db import SessionLocal
from app.tasks._background import fire_and_forget_or_defer_to_poller

logger = get_logger(__name__)


async def recompute_report_stats_detached(report_ids: list[int]) -> None:
    """Recompute report stats on a session of our own, then commit."""
    # Local import: carbon_report_service imports the module service, which
    # this module's callers import — top-level would cycle.
    from app.services.carbon_report_service import CarbonReportService

    if not report_ids:
        return
    async with SessionLocal() as session:
        await CarbonReportService(session).recompute_report_stats_many(
            sorted(report_ids)
        )
        await session.commit()
    logger.info(f"Report stats rolled up for {len(report_ids)} report(s) (detached)")


def schedule_report_rollup(report_ids: set[int]) -> None:
    """Dispatch the rollup for ``report_ids`` after the response.

    Call this *after* the route commits: the detached task reads the module
    stats the request wrote, so it must not start before they are visible.
    """
    if not report_ids:
        return
    fire_and_forget_or_defer_to_poller(
        recompute_report_stats_detached(sorted(report_ids)),
        name=f"report-rollup-{'-'.join(str(i) for i in sorted(report_ids))}",
    )
