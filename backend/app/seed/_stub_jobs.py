"""Stub ``DataIngestionJob`` rows for seed scripts (#1080 sprint-9).

The seed scripts (``seed_generic_factors.py`` /
``seed_generic_data_entries.py``) write factor and data-entry rows
directly through ``LocalFactorCSVProvider`` /
``LocalDataEntryCSVProvider``, bypassing the dispatch endpoint.
That keeps seeds fast and avoids the dispatch path's auth + year-
provisioning preconditions — but the data-management UI reads
``DataIngestionJob`` rows to render the "✓ <file> · N rows imported"
history on each card.  Without a matching job row, seeded
factors / entries show up in the DB while the cards stay blank.

``create_seed_stub_job`` plants a FINISHED + SUCCESS row that
mirrors what a real dispatch + provider would have written, minus:

* No ``pipeline_id`` — seeds bypass the chain entirely; orphan
  rows are honest about that and show up tagged ``(no pipeline)``
  in the pipeline-operations console.
* No ``processed_file_path`` — the seed CSV lives in
  ``backend/seed_data/``, not in the files store, and copying it
  in would require S3 access in non-local environments.  The
  card's download button hides when the key is absent (operator
  re-downloads from the repo if needed).
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.data_ingestion import (
    DataIngestionJob,
    EntityType,
    IngestionMethod,
    IngestionResult,
    IngestionState,
    TargetType,
)
from app.models.user import UserProvider


async def create_seed_stub_job(
    session: AsyncSession,
    *,
    module_type_id: int,
    data_entry_type_id: Optional[int],
    year: int,
    target_type: TargetType,
    job_type: str,
    file_path: Path,
    rows_processed: int,
    rows_skipped: int = 0,
) -> int:
    """Insert one FINISHED + SUCCESS ``DataIngestionJob`` for a seeded CSV.

    The shape mirrors what ``LocalFactorCSVProvider`` /
    ``LocalDataEntryCSVProvider`` would have written had they run
    via the dispatch endpoint, so the data-management cards pick
    the stub up as a normal "latest factor/data job" entry:

    * ``state=FINISHED``, ``result=SUCCESS``, ``finished_at`` set —
      ``compute_pipeline_progress`` treats the row as terminal.
    * ``is_current=True`` — ``get_latest_jobs_by_year`` joins on
      this column for the per-(module, det) latest pick.
    * ``meta`` carries ``file_path`` (drives the card's filename
      display via ``safeFileName``), ``rows_processed`` (the
      "N rows imported" line), and ``timestamp`` (the "·
      DD.MM.YYYY" suffix).  The synthetic ``seed/<filename>``
      prefix on ``file_path`` distinguishes seeded rows from real
      uploads (real uploads use ``tmp/<timestamp>/<filename>``).
    * ``status_message='Seeded'`` so the operator clicking the
      message column gets an honest "this was a seed, not an
      operator upload" signal.
    * ``ingestion_method=CSV`` because the seed providers reuse
      the CSV path internally; ``api`` / ``computed`` would put
      the row in the wrong section of ``_pick_latest_job``.

    No commit — the caller batches commits per seed config.
    Returns the new ``job_id`` so the caller can log it.
    """
    now = datetime.now(timezone.utc)
    filename = file_path.name
    job = DataIngestionJob(
        entity_type=EntityType.MODULE_PER_YEAR,
        module_type_id=module_type_id,
        data_entry_type_id=data_entry_type_id,
        year=year,
        target_type=target_type,
        ingestion_method=IngestionMethod.csv,
        provider=UserProvider.DEFAULT,
        state=IngestionState.FINISHED,
        result=IngestionResult.SUCCESS,
        status_message="Seeded",
        is_current=True,
        job_type=job_type,
        started_at=now,
        finished_at=now,
        meta={
            # ``seeded=True`` is a marker queryable by operators
            # (``WHERE meta->>'seeded' = 'true'``) for "show me
            # every row this seed produced".
            "seeded": True,
            # The card UI extracts the basename for display.  Using
            # a ``seed/`` prefix instead of a real path makes the
            # synthetic origin obvious if someone inspects the row
            # directly.
            "file_path": f"seed/{filename}",
            "rows_processed": rows_processed,
            "rows_skipped": rows_skipped,
            # ``timestamp`` is ISO8601 because the card's
            # ``getJobInfo`` passes it through ``new Date(...)``.
            "timestamp": now.isoformat(),
        },
    )
    session.add(job)
    await session.flush()
    return int(job.id) if job.id is not None else 0
