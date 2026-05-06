"""Plan 310-C handler bootstrap.

Importing this module eagerly imports every handler module so the
``@register("…")`` decorators run and populate the registry.  Without
these imports, ``run_job`` would raise ``ValueError: No handler
registered for job_type=…`` for any job_type whose handler module
hasn't been touched yet by some other code path.

Why a dedicated module instead of ``app/tasks/__init__.py``: the package
``__init__`` is loaded transitively from ``app.services.audit_service``
(which imports ``audit_sync_tasks``) and would create a circular import
back through the ingestion provider factory.  This module is imported
later in the boot sequence (from ``app.main``'s lifespan and from
``app.tasks.runner``'s first dispatch) when the audit graph is fully
loaded.

Side-effect-only imports — names are not re-exported.  ``noqa: F401``
silences ruff's "imported but unused" warning since the import IS the
intent here.
"""

_BOOTSTRAPPED = False


def bootstrap_handlers() -> None:
    """Idempotent: import the handler modules so their decorators fire.

    Safe to call from multiple sites (lifespan, runner first call) —
    a module-level guard makes repeats free.  Pure ``import`` would
    work as well, but the guard makes intent explicit when reading
    crash backtraces.
    """
    global _BOOTSTRAPPED
    if _BOOTSTRAPPED:
        return
    from app.tasks import (
        emission_recalculation_tasks,  # noqa: F401
        ingestion_tasks,  # noqa: F401
        unit_sync_tasks,  # noqa: F401
    )

    _BOOTSTRAPPED = True
