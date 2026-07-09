"""Regression test for module-type stat-bucket coverage.

Past LLM-session review flagged: the module → emission mapping was missing
an entry for ``research_facilities``.  Without it,
``CarbonReportModuleService.recompute_stats_many`` early-continues at
``if not bucket_nodes``, leaving ``carbon_report_modules.stats`` as None —
the dashboard's per-module totals broke silently.

This test pins ``MODULE_STAT_BUCKETS`` coverage so a future "add new module
type without declaring its buckets" regression trips at test time, not in
production aggregation runs.
"""

from app.models.module_type import ALL_MODULE_TYPE_IDS, ModuleTypeEnum
from app.modules.emissions import EmissionType
from app.modules.emissions.registry import MODULE_STAT_BUCKETS


def test_every_module_type_has_stat_buckets() -> None:
    """Every ``ModuleTypeEnum`` value MUST appear in ``MODULE_STAT_BUCKETS``
    with at least one bucket, or its stats stay unset while the aggregation
    chain still reports SUCCESS.
    """
    for module_id in ALL_MODULE_TYPE_IDS:
        module_type = ModuleTypeEnum(module_id)
        buckets = MODULE_STAT_BUCKETS.get(module_type)
        assert buckets, (
            f"{module_type.name!r} has no entry in MODULE_STAT_BUCKETS — "
            "recompute_stats will skip this module and leave its stats "
            "unset. Declare STAT_BUCKETS in the module's emissions.py and "
            "register it in the emissions registry."
        )


def test_research_facilities_has_explicit_bucket() -> None:
    """Pin the specific fix: research_facilities reports under one bucket
    rooted at ``EmissionType.research_facilities`` (value 100000), covering
    both leaves (facilities + animal).
    """
    buckets = MODULE_STAT_BUCKETS[ModuleTypeEnum.research_facilities]
    assert any(EmissionType.research_facilities in bn.bucket.roots for bn in buckets), (
        f"research_facilities buckets = "
        f"{[bn.bucket.key for bn in buckets]} — expected a bucket rooted at "
        "EmissionType.research_facilities."
    )
