"""Pure helpers over persisted carbon_report.stats dicts.

``derive_report_sections`` computes the display-derived sections (scope
totals, per-FTE, quantity donuts, IT rollup) from merged buckets; ``merge_report_stats``
combines several reports' stats into one aggregate of the same shape
(backoffice multi-unit views); ``build_year_comparison`` reshapes one
report's stats into the compare-years payload. None touch the database.
"""

from app.modules.emissions.registry import ORDERED_STAT_BUCKETS
from app.modules.emissions.taxonomy import resolve_emission_type
from app.modules.emissions.units import additional_value_unit
from app.utils.it_breakdown import (
    IT_CATEGORY_TO_BUCKET_KEY,
    build_cloud_ai_detail,
    build_it_category_totals,
)


def derive_quantity_sections(buckets: dict[str, dict]) -> dict[str, dict]:
    """Per-bucket physical-quantity breakdowns for the quantity donuts.

    Returns ``{bucket_key: {"unit": "km"|"kg", "by_emission_type":
    {emission_type_id: quantity}}}`` for buckets whose emission types carry an
    ``additional_value`` unit (commuting/professional_travel in km, food/waste
    in kg); other buckets are omitted.

    Ids are drawn from the union of ``by_emission_type`` and
    ``by_additional_value``, because a zero-emission mode (walking) has no kg
    entry but still carries kilometres. Only leaves are kept — an id whose
    dotted name prefixes another present id's name is a rollup whose subtree
    sum would double-count the donut.
    """
    sections: dict[str, dict] = {}
    for bucket_key, bucket in buckets.items():
        by_additional = bucket.get("by_additional_value") or {}
        if not by_additional:
            continue
        ids = set(bucket.get("by_emission_type") or {}) | set(by_additional)
        nodes = {
            id_str: node
            for id_str in ids
            if (node := resolve_emission_type(int(id_str))) is not None
        }
        names = {node.name for node in nodes.values()}
        unit: str | None = None
        by_emission_type: dict[str, float] = {}
        for id_str, node in nodes.items():
            quantity = by_additional.get(id_str)
            if not quantity or quantity <= 0:
                continue
            if any(name.startswith(f"{node.name}__") for name in names):
                continue
            node_unit = additional_value_unit(node)
            if node_unit is None:
                continue
            unit = node_unit
            by_emission_type[id_str] = float(quantity)
        if unit is not None and by_emission_type:
            sections[bucket_key] = {
                "unit": unit,
                "by_emission_type": by_emission_type,
            }
    return sections


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
    for category, bucket_key in IT_CATEGORY_TO_BUCKET_KEY.items():
        if bucket_key not in validated_buckets:
            continue
        validated_it_kg += it_category_kg.get(category, 0.0)
    validated_total_kg = sum(
        (buckets.get(key) or {}).get("total_kg", 0.0) or 0.0
        for key in validated_buckets
    )
    it_stats = {
        "total_kg": it_total_kg,
        "percentage_of_total": (
            it_total_kg / total_kg * 100.0 if total_kg > 0 else 0.0
        ),
        "per_fte": it_total_kg / total_fte / 1000.0 if total_fte > 0 else 0.0,
        "percentage_of_validated_total": (
            validated_it_kg / validated_total_kg * 100.0
            if validated_total_kg > 0
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
    return {
        **scope_totals,
        "per_fte": per_fte,
        "quantities": derive_quantity_sections(buckets),
        "it": it_stats,
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
