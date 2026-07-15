"""Pure helpers over persisted carbon_report.stats dicts.

``derive_report_sections`` computes the display-derived sections (scope
totals, per-FTE, IT rollup) from merged buckets; ``merge_report_stats``
combines several reports' stats into one aggregate of the same shape
(backoffice multi-unit views); ``build_year_comparison`` reshapes one
report's stats into the compare-years payload. None touch the database.
"""

from app.modules.emissions.registry import ORDERED_STAT_BUCKETS
from app.utils.it_breakdown import (
    IT_CATEGORY_TO_BUCKET_KEY,
    build_cloud_ai_detail,
    build_it_category_totals,
)


def derive_report_sections(
    buckets: dict[str, dict],
    by_emission_type: dict[str, float],
    total_kg: float,
    total_fte: float,
    top_class_detail: dict[str, list],
    validated_buckets: list[str],
) -> dict:
    """Derive scope totals, per-FTE values and the IT section from buckets."""
    scope_totals = {"scope1": 0.0, "scope2": 0.0, "scope3": 0.0}
    per_fte: dict[str, float] = {}
    for key, bucket in buckets.items():
        bucket_kg = bucket.get("total_kg", 0.0) or 0.0
        scope_totals[f"scope{bucket.get('scope', 3)}"] += bucket_kg
        per_fte[key] = bucket_kg / total_fte / 1000.0 if total_fte > 0 else 0.0

    it_category_kg = build_it_category_totals(by_emission_type)
    it_total_kg = sum(it_category_kg.values())
    validated_it_kg = 0.0
    validated_source_kg = 0.0
    for category, bucket_key in IT_CATEGORY_TO_BUCKET_KEY.items():
        if bucket_key not in validated_buckets:
            continue
        validated_it_kg += it_category_kg.get(category, 0.0)
        validated_source_kg += (buckets.get(bucket_key) or {}).get("total_kg", 0.0)
    it_stats = {
        "total_kg": it_total_kg,
        "percentage_of_total": (
            it_total_kg / total_kg * 100.0 if total_kg > 0 else 0.0
        ),
        "per_fte": it_total_kg / total_fte / 1000.0 if total_fte > 0 else 0.0,
        "percentage_of_source_modules": (
            validated_it_kg / validated_source_kg * 100.0
            if validated_source_kg > 0
            else 0.0
        ),
        "categories": it_category_kg,
        "cloud_ai_detail": build_cloud_ai_detail(by_emission_type),
        "validated_sources": [
            category
            for category, bucket_key in IT_CATEGORY_TO_BUCKET_KEY.items()
            if bucket_key in validated_buckets
        ],
        "top_class_detail": top_class_detail,
    }
    return {**scope_totals, "per_fte": per_fte, "it": it_stats}


def build_year_comparison(stats: dict) -> dict:
    """Reshape one report's persisted stats into a compare-years year entry.

    Args:
        stats: a persisted ``carbon_report.stats`` dict (or a
            ``merge_report_stats`` aggregate, which has the same shape).

    Returns:
        ``{"modules": {bucket_key: tonnes}, "scopes": {"1": t, "2": t,
        "3": t}, "total_tonnes_co2eq": t}``. ``modules`` is keyed by stat-bucket
        key -- including the additional buckets (commuting, food, waste,
        embodied_energy) -- so the stacked-bar segments match the Results
        category palette.

    Only buckets whose module is validated are counted, so a year's total
    matches the validated-only Results headline. An in-progress module is
    absent rather than zero, which keeps it out of the objective baselines
    too. Note this means the current year can read lower here than in the
    unit carbon footprint chart behind the dialog, which shows every module.

    Scopes are summed from the buckets rather than read off ``scope1/2/3``,
    which cover every module validated or not, so they stay consistent with
    the filtered ``modules`` above.
    """
    modules: dict[str, float] = {}
    scopes: dict[str, float] = {"1": 0.0, "2": 0.0, "3": 0.0}
    validated_keys = set(stats.get("validated_buckets") or [])

    for key, bucket in (stats.get("buckets") or {}).items():
        if key not in validated_keys:
            continue
        bucket_kg = bucket.get("total_kg", 0.0) or 0.0
        if bucket_kg <= 0:
            continue
        tonnes = bucket_kg / 1000.0
        modules[key] = tonnes
        scope_key = str(bucket.get("scope", 3))
        scopes[scope_key] = scopes.get(scope_key, 0.0) + tonnes

    return {
        "modules": modules,
        "scopes": scopes,
        "total_tonnes_co2eq": sum(modules.values()),
    }


# Bucket detail lists persisted alongside the numeric aggregates, mapped to the
# field naming each row. They are plain per-key kg sums (no top-N), so summing
# them across reports is exact: e.g. the same building in two units collapses
# into one row, as it should.
_BUCKET_DETAIL_NAME_FIELDS = {
    "by_building": "building_name",
    "by_category": "category",
}


def _merge_bucket_into(target: dict, bucket: dict) -> None:
    target["total_kg"] += bucket.get("total_kg", 0.0) or 0.0
    for et_id_str, kg in (bucket.get("by_emission_type") or {}).items():
        target["by_emission_type"][et_id_str] = (
            target["by_emission_type"].get(et_id_str, 0.0) + kg
        )
    for et_id_str, add_val in (bucket.get("by_additional_value") or {}).items():
        target["by_additional_value"][et_id_str] = target["by_additional_value"].get(
            et_id_str, 0.0
        ) + float(add_val)
    for detail_key, name_field in _BUCKET_DETAIL_NAME_FIELDS.items():
        rows = bucket.get(detail_key)
        if not rows:
            continue
        accumulator = target.setdefault(detail_key, {})
        for row in rows:
            name = row.get(name_field)
            if name is None:
                continue
            accumulator[name] = accumulator.get(name, 0.0) + (
                row.get("kg_co2eq") or 0.0
            )


def _finalize_bucket_details(bucket: dict) -> None:
    """Turn the name→kg accumulators back into the persisted row shape."""
    for detail_key, name_field in _BUCKET_DETAIL_NAME_FIELDS.items():
        raw_accumulator = bucket.get(detail_key)
        if not isinstance(raw_accumulator, dict):
            continue
        accumulator: dict[str, float] = raw_accumulator
        bucket[detail_key] = [
            {name_field: name, "kg_co2eq": kg, "tonnes_co2eq": kg / 1000.0}
            for name, kg in sorted(accumulator.items())
            if kg > 0
        ]


def merge_report_stats(stats_list: list[dict]) -> dict:
    """Merge several reports' stats into one aggregate of the same shape.

    Bucket detail lists (embodied energy by building / by category) are summed
    per key, so charts fed from them keep working on a combined perimeter.

    Per-unit top-class detail is dropped: a union of per-unit top-3 lists is
    not a meaningful aggregate.
    """
    buckets: dict[str, dict] = {}
    by_emission_type: dict[str, float] = {}
    by_additional_value: dict[str, float] = {}
    validated_buckets: list[str] = []
    total_kg = 0.0
    validated_total_kg = 0.0
    total_fte = 0.0
    entry_count = 0

    for _module_type, bucket_nodes in ORDERED_STAT_BUCKETS:
        key = bucket_nodes.bucket.key
        merged_bucket: dict | None = None
        for stats in stats_list:
            bucket = (stats.get("buckets") or {}).get(key)
            if not bucket:
                continue
            if merged_bucket is None:
                merged_bucket = {
                    "scope": bucket_nodes.bucket.scope,
                    "additional": bucket_nodes.bucket.additional,
                    "total_kg": 0.0,
                    "by_emission_type": {},
                    "by_additional_value": {},
                }
            _merge_bucket_into(merged_bucket, bucket)
        if merged_bucket is None:
            continue
        _finalize_bucket_details(merged_bucket)
        buckets[key] = merged_bucket
        for et_id_str, kg in merged_bucket["by_emission_type"].items():
            by_emission_type[et_id_str] = by_emission_type.get(et_id_str, 0.0) + kg
        for et_id_str, add_val in merged_bucket["by_additional_value"].items():
            by_additional_value[et_id_str] = (
                by_additional_value.get(et_id_str, 0.0) + add_val
            )

    for stats in stats_list:
        total_kg += stats.get("total", 0.0) or 0.0
        validated_total_kg += stats.get("validated_total", 0.0) or 0.0
        total_fte += stats.get("total_fte", 0.0) or 0.0
        entry_count += stats.get("entry_count", 0) or 0
        for key in stats.get("validated_buckets") or []:
            if key not in validated_buckets:
                validated_buckets.append(key)

    return {
        "buckets": buckets,
        "validated_buckets": validated_buckets,
        "total": total_kg,
        "validated_total": validated_total_kg,
        "total_fte": total_fte,
        "by_emission_type": by_emission_type,
        "by_additional_value": by_additional_value,
        "entry_count": entry_count,
        **derive_report_sections(
            buckets,
            by_emission_type,
            total_kg,
            total_fte,
            top_class_detail={},
            validated_buckets=validated_buckets,
        ),
    }
