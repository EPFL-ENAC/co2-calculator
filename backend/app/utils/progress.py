"""Shared progress-line formatting for long-running jobs.

One format for every job status line (CSV ingest, emission recalc, …) so
the ops console reads consistently and rate/ETA math lives in one place.
"""


def format_progress(
    phase: str,
    processed: int | None,
    total: int | None,
    elapsed: float,
    unit: str = "rows",
) -> str:
    """Human-readable progress line with throughput + rough ETA."""
    if not processed or not total:
        return phase
    rate = processed / max(elapsed, 1e-3)
    eta = (total - processed) / rate if rate > 0 else 0.0
    return f"{phase}: {processed}/{total} {unit} ({rate:.0f}/s, ~{eta:.0f}s left)"
