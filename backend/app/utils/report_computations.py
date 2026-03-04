"""Pure functions for computing validated totals and results summary.

Extracted from carbon_report_module_stats routes so they can be unit tested
without DB or HTTP dependencies. Follows the same pattern as
utils/emission_breakdown.py.
"""


def compute_validated_totals(
    emission_stats: dict[str, float],
    fte_stats: dict[str, float],
    headcount_type_id: str,
) -> dict:
    """Build the validated-totals response from raw per-module aggregates.

    For the headcount module, FTE is used as the display value (if available);
    all other modules convert kg → tonnes.  ``total_tonnes_co2eq`` always sums
    emission values (including headcount emissions) in tonnes.

    Args:
        emission_stats: ``{module_type_id_str: sum_kg_co2eq}``
        fte_stats: ``{module_type_id_str: sum_fte}``
        headcount_type_id: string form of ``ModuleTypeEnum.headcount.value``
    """
    all_module_ids = set(emission_stats.keys()) | set(fte_stats.keys())

    modules: dict[int, float] = {}
    for module_type_id in sorted(all_module_ids, key=int):
        if module_type_id == headcount_type_id and module_type_id in fte_stats:
            modules[int(module_type_id)] = fte_stats[module_type_id]
        elif module_type_id in emission_stats:
            modules[int(module_type_id)] = emission_stats[module_type_id] / 1000.0

    total_kg_co2eq = sum(emission_stats.values())
    total_tonnes_co2eq = total_kg_co2eq / 1000.0
    total_fte = sum(fte_stats.values())

    return {
        "modules": modules,
        "total_tonnes_co2eq": total_tonnes_co2eq,
        "total_fte": total_fte,
    }


def compute_results_summary(
    current_emissions: dict[str, float | None],
    current_fte: dict[str, float | None],
    prev_emissions: dict[str, float],
    co2_per_km_kg: float,
    headcount_key: str,
) -> dict:
    """Build the results-summary response from raw emission/FTE data.

    All division-by-zero and missing-data guards are handled here so callers
    don't need to worry about ``None`` propagation.

    Args:
        current_emissions: ``{module_type_id_str: kg_co2eq | None}``
        current_fte: ``{module_type_id_str: fte}``
        prev_emissions: ``{module_type_id_str: kg_co2eq}`` (empty if no prev year)
        co2_per_km_kg: conversion factor for equivalent car km (must be > 0)
        headcount_key: string form of ``ModuleTypeEnum.headcount.value``

    Raises:
        ValueError: If *co2_per_km_kg* is zero or negative.
    """
    if co2_per_km_kg <= 0:
        raise ValueError(f"co2_per_km_kg must be positive, got {co2_per_km_kg}")

    total_fte = current_fte.get(headcount_key)

    # --- Per-module results ---
    module_results: list[dict] = []
    for module_key, kg_co2eq in current_emissions.items():
        if kg_co2eq is None:
            continue
        total_tonnes = kg_co2eq / 1000
        tonnes_per_fte = (
            (total_tonnes / total_fte) if total_fte and total_fte > 0 else None
        )
        equivalent_car_km = kg_co2eq / co2_per_km_kg

        prev_kg = prev_emissions.get(module_key)
        prev_tonnes = prev_kg / 1000 if prev_kg is not None else None
        year_comparison = None
        if prev_kg is not None and prev_kg > 0:
            year_comparison = (kg_co2eq - prev_kg) / prev_kg * 100

        module_results.append(
            {
                "module_type_id": int(module_key),
                "total_tonnes_co2eq": total_tonnes,
                "total_fte": total_fte if module_key == headcount_key else None,
                "tonnes_co2eq_per_fte": tonnes_per_fte,
                "equivalent_car_km": equivalent_car_km,
                "previous_year_total_tonnes_co2eq": prev_tonnes,
                "year_comparison_percentage": year_comparison,
            }
        )

    # --- Unit totals ---
    non_none_emissions = [v for v in current_emissions.values() if v is not None]
    non_none_prev = [v for v in prev_emissions.values() if v is not None]
    total_kg: float | None = sum(non_none_emissions) if non_none_emissions else None
    total_prev_kg: float | None = sum(non_none_prev) if non_none_prev else None
    total_tonnes_all = total_kg / 1000 if total_kg is not None else None
    total_tonnes_per_fte = (
        (total_tonnes_all / total_fte)
        if total_tonnes_all is not None and total_fte and total_fte > 0
        else None
    )
    total_car_km = total_kg / co2_per_km_kg if total_kg is not None else None
    total_year_comparison = None
    if total_prev_kg is not None and total_kg is not None and total_prev_kg > 0:
        total_year_comparison = (total_kg - total_prev_kg) / total_prev_kg * 100

    return {
        "unit_totals": {
            "total_tonnes_co2eq": total_tonnes_all,
            "total_fte": total_fte,
            "tonnes_co2eq_per_fte": total_tonnes_per_fte,
            "equivalent_car_km": total_car_km,
            "previous_year_total_tonnes_co2eq": (
                total_prev_kg / 1000 if total_prev_kg is not None else None
            ),
            "year_comparison_percentage": total_year_comparison,
        },
        "co2_per_km_kg": co2_per_km_kg,
        "module_results": module_results,
    }
