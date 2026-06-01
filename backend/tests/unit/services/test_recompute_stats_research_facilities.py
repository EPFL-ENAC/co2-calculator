"""Regression test for the research_facilities recompute-stats gap.

Past LLM-session review flagged: ``MODULE_TYPE_TO_EMISSION_ROOTS`` was
missing an entry for ``research_facilities``.  Without it,
``CarbonReportModuleService.recompute_stats`` early-returned at
``if not emission_roots: return`` (see
``carbon_report_module_service.py:283``), leaving
``carbon_report_modules.stats`` as None for every research_facilities
module — the dashboard's per-module totals broke silently.

This test pins the map's coverage so a future "add new module type
without updating the roots" regression trips at import time, not in
production aggregation runs.
"""

from app.models.module_type import (
    ALL_MODULE_TYPE_IDS,
    MODULE_TYPE_TO_EMISSION_ROOTS,
    ModuleTypeEnum,
)


def test_every_module_type_has_emission_roots() -> None:
    """Every ``ModuleTypeEnum`` value in ``ALL_MODULE_TYPE_IDS`` MUST
    appear as a key in ``MODULE_TYPE_TO_EMISSION_ROOTS`` with a
    non-empty list.

    ``recompute_stats`` falls back to ``return`` on a missing or
    empty entry, leaving the module's ``stats`` column unset.  The
    aggregation chain still reports SUCCESS, so the regression is
    invisible to the runner — only the dashboard reveals it via
    missing per-module totals.
    """
    for module_id in ALL_MODULE_TYPE_IDS:
        module_type = ModuleTypeEnum(module_id)
        roots = MODULE_TYPE_TO_EMISSION_ROOTS.get(module_type)
        assert roots, (
            f"{module_type.name!r} has no entry in "
            "MODULE_TYPE_TO_EMISSION_ROOTS — recompute_stats will "
            "early-return for this module and leave its stats unset. "
            "Add the EmissionType root(s) whose subtree covers every "
            "emission_type_id that can appear under this module."
        )


def test_research_facilities_has_explicit_root() -> None:
    """Pin the specific fix: ``research_facilities`` rolls up to
    ``EmissionType.research_facilities`` (value 100000) per
    ``EMISSION_TYPE_PARENT_MAP``.  The two leaves
    (``research_facilities__facilities`` = 100100 +
    ``research_facilities__animal`` = 100200) both share this root.
    """
    from app.models.data_entry_emission import EmissionType

    roots = MODULE_TYPE_TO_EMISSION_ROOTS[ModuleTypeEnum.research_facilities]
    assert EmissionType.research_facilities in roots, (
        f"research_facilities module roots = {[r.name for r in roots]} — "
        "expected EmissionType.research_facilities as the rollup root."
    )
