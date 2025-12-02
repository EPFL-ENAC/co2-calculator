"""Backoffice API endpoints."""

from datetime import datetime, timedelta
from typing import Any, List, Optional, cast

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.api.deps import get_current_active_user
from app.core.logging import get_logger
from app.models.user import User

logger = get_logger(__name__)
router = APIRouter()


# Mock data for backoffice reporting
MOCK_UNITS_REPORTING = [
    {
        "id": 1,
        "completion": {
            "2024": {
                "my_lab": {"status": "default", "outlier_values": 3},
                "professional_travel": {"status": "in-progress", "outlier_values": 2},
                "infrastructure": {"status": "default", "outlier_values": 0},
                "equipment_electric_consumption": {
                    "status": "default",
                    "outlier_values": 0,
                },
                "purchase": {"status": "default", "outlier_values": 0},
                "internal_services": {"status": "validated", "outlier_values": 0},
                "external_cloud": {"status": "validated", "outlier_values": 0},
            },
            "2025": {
                "my_lab": {"status": "in-progress", "outlier_values": 3},
                "professional_travel": {"status": "in-progress", "outlier_values": 2},
                "infrastructure": {"status": "default", "outlier_values": 0},
                "equipment_electric_consumption": {
                    "status": "default",
                    "outlier_values": 0,
                },
                "purchase": {"status": "default", "outlier_values": 0},
                "internal_services": {"status": "validated", "outlier_values": 7},
                "external_cloud": {"status": "validated", "outlier_values": 0},
            },
            "2026": {
                "my_lab": {"status": "in-progress", "outlier_values": 3},
                "professional_travel": {"status": "in-progress", "outlier_values": 2},
                "infrastructure": {"status": "default", "outlier_values": 4},
                "equipment_electric_consumption": {
                    "status": "default",
                    "outlier_values": 0,
                },
                "purchase": {"status": "default", "outlier_values": 0},
                "internal_services": {"status": "validated", "outlier_values": 0},
                "external_cloud": {"status": "validated", "outlier_values": 0},
            },
        },
        "unit": "ALICE",
        "affiliation": "ENAC",
        "principal_user": "Charlie Weil",
        "last_update": datetime.now() - timedelta(days=2),
    },
    {
        "id": 2,
        "completion": {
            "2024": {
                "my_lab": {"status": "in-progress", "outlier_values": 2},
                "professional_travel": {"status": "in-progress", "outlier_values": 3},
                "infrastructure": {"status": "default", "outlier_values": 0},
                "equipment_electric_consumption": {
                    "status": "default",
                    "outlier_values": 0,
                },
                "purchase": {"status": "default", "outlier_values": 0},
                "internal_services": {"status": "validated", "outlier_values": 0},
                "external_cloud": {"status": "validated", "outlier_values": 0},
            },
            "2025": {
                "my_lab": {"status": "in-progress", "outlier_values": 2},
                "professional_travel": {"status": "in-progress", "outlier_values": 3},
                "infrastructure": {"status": "default", "outlier_values": 0},
                "equipment_electric_consumption": {
                    "status": "default",
                    "outlier_values": 0,
                },
                "purchase": {"status": "default", "outlier_values": 0},
                "internal_services": {"status": "validated", "outlier_values": 0},
                "external_cloud": {"status": "validated", "outlier_values": 0},
            },
            "2026": {
                "my_lab": {"status": "in-progress", "outlier_values": 2},
                "professional_travel": {"status": "in-progress", "outlier_values": 3},
                "infrastructure": {"status": "default", "outlier_values": 0},
                "equipment_electric_consumption": {
                    "status": "default",
                    "outlier_values": 0,
                },
                "purchase": {"status": "default", "outlier_values": 0},
                "internal_services": {"status": "validated", "outlier_values": 0},
                "external_cloud": {"status": "validated", "outlier_values": 0},
            },
        },
        "unit": "ISREC",
        "affiliation": "SV",
        "principal_user": "Benjamin Botros",
        "last_update": datetime.now() - timedelta(hours=5),
    },
    {
        "id": 3,
        "completion": {
            "2024": {
                "my_lab": {"status": "validated", "outlier_values": 0},
                "professional_travel": {"status": "in-progress", "outlier_values": 4},
                "infrastructure": {"status": "default", "outlier_values": 0},
                "equipment_electric_consumption": {
                    "status": "default",
                    "outlier_values": 0,
                },
                "purchase": {"status": "default", "outlier_values": 0},
                "internal_services": {"status": "validated", "outlier_values": 0},
                "external_cloud": {"status": "validated", "outlier_values": 8},
            },
            "2025": {
                "my_lab": {"status": "validated", "outlier_values": 0},
                "professional_travel": {"status": "in-progress", "outlier_values": 4},
                "infrastructure": {"status": "default", "outlier_values": 0},
                "equipment_electric_consumption": {
                    "status": "default",
                    "outlier_values": 0,
                },
                "purchase": {"status": "default", "outlier_values": 0},
                "internal_services": {"status": "validated", "outlier_values": 0},
                "external_cloud": {"status": "validated", "outlier_values": 8},
            },
            "2026": {
                "my_lab": {"status": "validated", "outlier_values": 0},
                "professional_travel": {"status": "in-progress", "outlier_values": 4},
                "infrastructure": {"status": "default", "outlier_values": 0},
                "equipment_electric_consumption": {
                    "status": "default",
                    "outlier_values": 0,
                },
                "purchase": {"status": "default", "outlier_values": 0},
                "internal_services": {"status": "validated", "outlier_values": 0},
                "external_cloud": {"status": "validated", "outlier_values": 8},
            },
        },
        "unit": "Network Architecture",
        "affiliation": "IC",
        "principal_user": "Nicolas Dubois",
        "last_update": datetime.now() - timedelta(days=1),
    },
    {
        "id": 4,
        "completion": {
            "2024": {
                "my_lab": {"status": "validated", "outlier_values": 0},
                "professional_travel": {"status": "validated", "outlier_values": 0},
                "infrastructure": {"status": "validated", "outlier_values": 2},
                "equipment_electric_consumption": {
                    "status": "validated",
                    "outlier_values": 0,
                },
                "purchase": {"status": "validated", "outlier_values": 1},
                "internal_services": {"status": "validated", "outlier_values": 0},
                "external_cloud": {"status": "validated", "outlier_values": 1},
            },
            "2025": {
                "my_lab": {"status": "validated", "outlier_values": 0},
                "professional_travel": {"status": "validated", "outlier_values": 0},
                "infrastructure": {"status": "validated", "outlier_values": 2},
                "equipment_electric_consumption": {
                    "status": "validated",
                    "outlier_values": 0,
                },
                "purchase": {"status": "validated", "outlier_values": 1},
                "internal_services": {"status": "validated", "outlier_values": 0},
                "external_cloud": {"status": "validated", "outlier_values": 1},
            },
            "2026": {
                "my_lab": {"status": "validated", "outlier_values": 0},
                "professional_travel": {"status": "validated", "outlier_values": 0},
                "infrastructure": {"status": "validated", "outlier_values": 2},
                "equipment_electric_consumption": {
                    "status": "validated",
                    "outlier_values": 0,
                },
                "purchase": {"status": "validated", "outlier_values": 1},
                "internal_services": {"status": "validated", "outlier_values": 0},
                "external_cloud": {"status": "validated", "outlier_values": 1},
            },
        },
        "unit": "Another Unit",
        "affiliation": "ENAC",
        "principal_user": "Alice Smith",
        "last_update": datetime.now() - timedelta(days=1),
    },
    {
        "id": 5,
        "completion": {
            "2024": {
                "my_lab": {"status": "validated", "outlier_values": 0},
                "professional_travel": {"status": "in-progress", "outlier_values": 0},
                "infrastructure": {"status": "in-progress", "outlier_values": 0},
                "equipment_electric_consumption": {
                    "status": "default",
                    "outlier_values": 0,
                },
                "purchase": {"status": "default", "outlier_values": 0},
                "internal_services": {"status": "validated", "outlier_values": 0},
                "external_cloud": {"status": "validated", "outlier_values": 0},
            },
            "2025": {
                "my_lab": {"status": "validated", "outlier_values": 0},
                "professional_travel": {"status": "in-progress", "outlier_values": 0},
                "infrastructure": {"status": "in-progress", "outlier_values": 0},
                "equipment_electric_consumption": {
                    "status": "default",
                    "outlier_values": 0,
                },
                "purchase": {"status": "default", "outlier_values": 0},
                "internal_services": {"status": "validated", "outlier_values": 0},
                "external_cloud": {"status": "validated", "outlier_values": 0},
            },
            "2026": {
                "my_lab": {"status": "validated", "outlier_values": 0},
                "professional_travel": {"status": "in-progress", "outlier_values": 0},
                "infrastructure": {"status": "in-progress", "outlier_values": 0},
                "equipment_electric_consumption": {
                    "status": "default",
                    "outlier_values": 0,
                },
                "purchase": {"status": "default", "outlier_values": 0},
                "internal_services": {"status": "validated", "outlier_values": 0},
                "external_cloud": {"status": "validated", "outlier_values": 0},
            },
        },
        "unit": "Research Group",
        "affiliation": "SV",
        "principal_user": "Bob Johnson",
        "last_update": datetime.now() - timedelta(hours=10),
    },
    {
        "id": 6,
        "completion": {
            "2024": {
                "my_lab": {"status": "default", "outlier_values": 0},
                "professional_travel": {"status": "default", "outlier_values": 0},
                "infrastructure": {"status": "default", "outlier_values": 0},
                "equipment_electric_consumption": {
                    "status": "default",
                    "outlier_values": 0,
                },
                "purchase": {"status": "default", "outlier_values": 0},
                "internal_services": {"status": "default", "outlier_values": 0},
                "external_cloud": {"status": "default", "outlier_values": 0},
            },
            "2025": {
                "my_lab": {"status": "default", "outlier_values": 0},
                "professional_travel": {"status": "default", "outlier_values": 0},
                "infrastructure": {"status": "default", "outlier_values": 0},
                "equipment_electric_consumption": {
                    "status": "default",
                    "outlier_values": 0,
                },
                "purchase": {"status": "default", "outlier_values": 0},
                "internal_services": {"status": "default", "outlier_values": 0},
                "external_cloud": {"status": "default", "outlier_values": 0},
            },
            "2026": {
                "my_lab": {"status": "default", "outlier_values": 0},
                "professional_travel": {"status": "default", "outlier_values": 0},
                "infrastructure": {"status": "default", "outlier_values": 0},
                "equipment_electric_consumption": {
                    "status": "default",
                    "outlier_values": 0,
                },
                "purchase": {"status": "default", "outlier_values": 0},
                "internal_services": {"status": "default", "outlier_values": 0},
                "external_cloud": {"status": "default", "outlier_values": 0},
            },
        },
        "unit": "New Lab",
        "affiliation": "IC",
        "principal_user": "Eve Brown",
        "last_update": datetime.now() - timedelta(days=5),
    },
]


class CompletionCounts(BaseModel):
    validated: int
    in_progress: int
    default: int


class ModuleCompletion(BaseModel):
    status: str  # "validated", "in-progress", "default"
    outlier_values: int


class UnitReportingData(BaseModel):
    id: int
    completion: dict[str, Any]
    completion_counts: CompletionCounts
    unit: str
    affiliation: str
    principal_user: str
    last_update: datetime
    outlier_values: (
        int  # Total outlier values (sum of all modules across selected years)
    )
    expected_total: Optional[int] = (
        None  # Expected total module-year combinations (7 × number of years)
    )


def get_module_status(module_data: dict | str) -> str:
    """Extract status from module data
    (handles both old string format and new object format)."""
    if isinstance(module_data, dict):
        return module_data.get("status", "default")
    return module_data if isinstance(module_data, str) else "default"


def get_module_outlier_values(module_data: dict | str) -> int:
    """
    Extract outlier_values from module data
    (handles both old string format and new object format).
    """
    if isinstance(module_data, dict):
        return module_data.get("outlier_values", 0)
    return 0


def _is_year_based(completion: dict) -> bool:
    """Check if completion data is year-based (has year keys like '2024', '2025')."""
    return any(
        isinstance(key, str) and key.isdigit() and len(key) == 4
        for key in completion.keys()
    )


def _get_year_keys(completion: dict) -> list[str]:
    """Extract all year keys from completion data."""
    return [
        k
        for k in completion.keys()
        if isinstance(k, str) and k.isdigit() and len(k) == 4
    ]


def _get_years_to_process(
    completion: dict, years: list[str] | None = None
) -> list[str]:
    """
    Get list of years to process
    defaulting to all available years if none specified.
    """
    if years:
        year_keys = set(_get_year_keys(completion))
        return [str(y).strip() for y in years if str(y).strip() in year_keys]
    return _get_year_keys(completion)


def get_completion_for_years(completion: dict, years: list[str] | None = None) -> dict:
    """
    Extract completion data for selected years.
    If years is None or empty, returns all years aggregated.
    If completion is old format (no years), returns it as-is.
    """
    if not _is_year_based(completion):
        return completion

    years_to_process = _get_years_to_process(completion, years)
    aggregated: dict[str, dict[str, Any]] = {}
    status_order = {"validated": 3, "in-progress": 2, "default": 1}

    for year in years_to_process:
        year_data = completion.get(year, {})
        if not isinstance(year_data, dict):
            continue

        for module_name, module_data in year_data.items():
            existing_module = aggregated.get(module_name)
            current_status = get_module_status(
                existing_module if existing_module else {}
            )
            new_status = get_module_status(module_data)
            new_outlier = get_module_outlier_values(module_data)

            if module_name not in aggregated:
                aggregated[module_name] = {
                    "status": new_status,
                    "outlier_values": new_outlier,
                }
            else:
                # Use best status, sum outlier values
                if status_order.get(new_status, 0) > status_order.get(
                    current_status, 0
                ):
                    aggregated[module_name]["status"] = new_status
                current_outlier = aggregated[module_name].get("outlier_values", 0)
                if isinstance(current_outlier, int):
                    aggregated[module_name]["outlier_values"] = (
                        current_outlier + new_outlier
                    )

    return aggregated


def calculate_completion_counts(
    completion: dict, years: list[str] | None = None
) -> CompletionCounts:
    """
    Calculate counts for each completion status across all selected years.
    Returns total validated/in-progress/default module-year combinations.
    """
    if not _is_year_based(completion):
        # Old format - count by module
        counts = {"validated": 0, "in_progress": 0, "default": 0}
        for module_data in completion.values():
            status = get_module_status(module_data)
            if status == "validated":
                counts["validated"] += 1
            elif status == "in-progress":
                counts["in_progress"] += 1
            else:
                counts["default"] += 1
        return CompletionCounts(**counts)

    years_to_check = _get_years_to_process(completion, years)
    counts = {"validated": 0, "in_progress": 0, "default": 0}

    for year_str in years_to_check:
        year_data = completion.get(year_str, {})
        if not isinstance(year_data, dict):
            continue

        for module_data in year_data.values():
            status = get_module_status(module_data)
            if status == "validated":
                counts["validated"] += 1
            elif status == "in-progress":
                counts["in_progress"] += 1
            else:
                counts["default"] += 1

    return CompletionCounts(**counts)


def calculate_total_outlier_values(
    completion: dict, years: list[str] | None = None
) -> int:
    """
    Calculate total outlier values by summing all module outlier_values,
    optionally filtered by years.
    """
    completion_data = get_completion_for_years(completion, years)
    total = 0
    for module_data in completion_data.values():
        total += get_module_outlier_values(module_data)
    return total


def _is_unit_complete(completion: dict, years: list[str] | None = None) -> bool:
    """
    Check if a unit is complete: all modules must be validated in ALL selected years.
    If no years selected, checks all years.
    Total required: 7 modules × number of years
    """
    if not _is_year_based(completion):
        return len(completion) == 7 and all(
            get_module_status(module_data) == "validated"
            for module_data in completion.values()
        )

    years_to_check = _get_years_to_process(completion, years)
    expected_total = 7 * len(years_to_check)
    validated_count = sum(
        1
        for year in years_to_check
        for module_data in completion.get(year, {}).values()
        if get_module_status(module_data) == "validated"
    )

    return validated_count == expected_total


@router.get("/units", response_model=List[UnitReportingData])
async def list_backoffice_units(
    affiliation: Optional[List[str]] = Query(
        None, description="Filter by affiliation(s) - can specify multiple"
    ),
    units: Optional[List[str]] = Query(
        None, description="Filter by unit name(s) - can specify multiple"
    ),
    completion: Optional[str] = Query(
        None, description="Filter by completion status (complete, incomplete)"
    ),
    outlier_values: Optional[bool] = Query(
        None,
        description="""Filter by outlier values (true = has outliers,
        false = no outliers)""",
    ),
    search: Optional[str] = Query(
        None, description="Search in unit name, affiliation, or principal user"
    ),
    modules: Optional[List[str]] = Query(
        None,
        description="""Filter by module states, format: 'module_name:state'
        (e.g., 'my_lab:validated')""",
    ),
    years: Optional[List[str]] = Query(
        None, description="Filter by years (e.g., ['2024', '2025'])"
    ),
    current_user: User = Depends(get_current_active_user),
):
    """
    List units with reporting data for backoffice.

    Returns mock data with completion status, outlier values, and other metrics.
    Supports filtering by affiliation, completion status, outlier values, and search.
    """
    filtered_units = MOCK_UNITS_REPORTING.copy()

    # Filter by affiliation(s)
    if affiliation:
        affiliation_set = {
            a.strip() for a in affiliation if isinstance(a, str) and a.strip()
        }
        if affiliation_set:
            filtered_units = [
                u for u in filtered_units if u["affiliation"] in affiliation_set
            ]

    # Filter by unit name(s)
    if units:
        units_set = {u.strip() for u in units if isinstance(u, str) and u.strip()}
        if units_set:
            filtered_units = [u for u in filtered_units if u["unit"] in units_set]

    # Filter by completion status (only if provided and not empty)
    if completion and isinstance(completion, str) and completion.strip():
        completion_status = completion.strip()
        if completion_status == "complete":
            # Filter units where all modules are validated in ALL selected years
            filtered_units = [
                u
                for u in filtered_units
                if isinstance(u.get("completion"), dict)
                and _is_unit_complete(cast(dict[str, Any], u["completion"]), years)
            ]
        elif completion_status == "incomplete":
            # Filter units that are not complete
            filtered_units = [
                u
                for u in filtered_units
                if not (
                    isinstance(u.get("completion"), dict)
                    and _is_unit_complete(cast(dict[str, Any], u["completion"]), years)
                )
            ]

    # Filter by outlier values
    if outlier_values is not None:
        filtered_units = [
            u
            for u in filtered_units
            if isinstance(u.get("completion"), dict)
            and (
                calculate_total_outlier_values(
                    cast(dict[str, Any], u["completion"]), years
                )
                > 0
            )
            == outlier_values
        ]

    # Filter by module states (only if provided and not empty)
    if modules and isinstance(modules, list) and len(modules) > 0:
        if any(isinstance(m, str) and m.strip() == "" for m in modules):
            filtered_units = []
        else:
            from collections import defaultdict

            module_filters_dict: dict[str, set[str]] = defaultdict(set)
            for module_filter in modules:
                if isinstance(module_filter, str) and ":" in module_filter:
                    parts = module_filter.split(":", 1)
                    if len(parts) == 2:
                        module_name = parts[0].strip()
                        state = parts[1].strip()
                        if module_name and state:  # Both must be non-empty
                            module_filters_dict[module_name].add(state)

            if module_filters_dict:
                filtered_units = [
                    u
                    for u in filtered_units
                    if isinstance(u.get("completion"), dict)
                    and all(
                        get_module_status(
                            get_completion_for_years(
                                cast(dict[str, Any], u["completion"]), years
                            ).get(module_name, {})
                        )
                        in states
                        for module_name, states in module_filters_dict.items()
                    )
                ]

    # Filter by search
    if search:
        search_lower = search.strip().lower()
        if search_lower:
            filtered_units = [
                u
                for u in filtered_units
                if any(
                    search_lower in str(u[field]).lower()
                    for field in ["unit", "affiliation", "principal_user"]
                )
            ]

    # Calculate expected total: 7 modules × number of selected years
    MODULE_COUNT = 7
    if years:
        num_years = len(years)
    elif filtered_units:
        completion_data = filtered_units[0].get("completion", {})
        if isinstance(completion_data, dict):
            num_years = len(_get_year_keys(completion_data)) or 3
        else:
            num_years = 3
    else:
        num_years = 3
    expected_total = MODULE_COUNT * num_years

    # Add completion counts and total outlier values to each unit
    result_units = []
    for unit in filtered_units:
        unit_dict = unit.copy()
        completion_data = unit.get("completion")
        if isinstance(completion_data, dict):
            completion_dict = cast(dict[str, Any], completion_data)
            unit_dict["completion"] = get_completion_for_years(completion_dict, years)
            unit_dict["completion_counts"] = calculate_completion_counts(
                completion_dict, years
            )
            unit_dict["outlier_values"] = calculate_total_outlier_values(
                completion_dict, years
            )
        else:
            unit_dict["completion"] = (
                completion_data if completion_data is not None else {}
            )
            unit_dict["completion_counts"] = CompletionCounts(
                validated=0, in_progress=0, default=0
            )
            unit_dict["outlier_values"] = 0
        unit_dict["expected_total"] = expected_total
        result_units.append(unit_dict)

    return result_units


@router.get("/unit/{unit_id}", response_model=UnitReportingData)
async def get_backoffice_unit(
    unit_id: int,
    years: Optional[List[str]] = Query(
        None, description="Filter by years (e.g., ['2024', '2025'])"
    ),
    current_user: User = Depends(get_current_active_user),
):
    """
    Get a unit with reporting data for backoffice.
    Returns raw completion data with all years if no years specified.
    """

    # Find unit by id
    unit = next((u for u in MOCK_UNITS_REPORTING if u["id"] == unit_id), None)
    if unit is None:
        raise HTTPException(
            status_code=404,
            detail=f"Unit with id {unit_id} not found",
        )

    unit_dict = unit.copy()
    MODULE_COUNT = 7

    completion_data = unit.get("completion", {})
    if isinstance(completion_data, dict):
        completion_dict = cast(dict[str, Any], completion_data)
        if years:
            num_years = len(years)
            unit_dict["completion"] = get_completion_for_years(completion_dict, years)
        else:
            unit_dict["completion"] = completion_dict
            num_years = len(_get_year_keys(completion_dict)) or 3

        unit_dict["completion_counts"] = calculate_completion_counts(
            completion_dict, years
        )
        unit_dict["outlier_values"] = calculate_total_outlier_values(
            completion_dict, years
        )
    else:
        unit_dict["completion"] = completion_data
        num_years = 3
        unit_dict["completion_counts"] = CompletionCounts(
            validated=0, in_progress=0, default=0
        )
        unit_dict["outlier_values"] = 0

    unit_dict["expected_total"] = MODULE_COUNT * num_years

    return unit_dict


@router.get("/years")
async def get_available_years(
    current_user: User = Depends(get_current_active_user),
):
    """
    Get all available years from all units combined.
    Returns all unique years found across all units' completion data,
    sorted in descending order (latest first).
    """
    all_years: set[str] = set()

    for unit in MOCK_UNITS_REPORTING:
        completion_data = unit.get("completion", {})
        if isinstance(completion_data, dict):
            years = _get_year_keys(completion_data)
            all_years.update(years)

    if not all_years:
        # Default to current year if no years found
        current_year = str(datetime.now().year)
        return {"years": [current_year], "latest": current_year}

    # Sort years in descending order (latest first)
    sorted_years = sorted(
        all_years, key=lambda y: int(y) if y.isdigit() else 0, reverse=True
    )
    latest_year = sorted_years[0]

    return {"years": sorted_years, "latest": latest_year}
