"""Year configuration schemas for API request/response validation."""

import csv
import io
from datetime import datetime
from enum import IntEnum
from typing import (
    Any,
    Dict,
    List,
    Literal,
    Optional,
    Type,
)

from pydantic import (
    BaseModel,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

# Type definitions
UncertaintyTag = Literal["low", "medium", "high", "none"]
FileCategory = Literal["footprint", "population", "scenarios"]


class FileMetadata(BaseModel):
    """Metadata for uploaded files."""

    path: str = Field(..., description="Storage path for the file")
    filename: str = Field(..., description="Original filename")
    uploaded_at: str = Field(..., description="Upload timestamp in ISO format")


# ---------------------------------------------------------------------------
# Reduction-objective CSV row models
# ---------------------------------------------------------------------------


# TODO: use this instead of the csv validation? DTO create equivalent?
class InstitutionalFootprintRow(BaseModel):
    """Single row of an institutional_footprint CSV."""

    year: int = Field(..., description="Reference year")
    category: str = Field(..., description="Emission category (e.g. energy, food)")
    co2: float = Field(..., description="CO2 equivalent in tCO2eq")

    @field_validator("co2")
    @classmethod
    def co2_must_be_non_negative(cls, v: float) -> float:
        if v < 0:
            raise ValueError(f"co2 must be >= 0, got {v}")
        return v


class PopulationProjectionRow(BaseModel):
    """Single row of a population_projections CSV."""

    year: int = Field(..., description="Reference year")
    pop: int = Field(..., description="Population headcount")

    @field_validator("pop")
    @classmethod
    def pop_must_be_non_negative(cls, v: int) -> int:
        if v < 0:
            raise ValueError(f"pop must be >= 0, got {v}")
        return v


class UnitScenarioRow(BaseModel):
    """Single row of a unit_scenarios CSV."""

    scenario: str = Field(..., description="Scenario name / label")
    year: int = Field(..., description="Reference year")
    reduction_percentage: float = Field(
        ...,
        description="Reduction fraction (0.0 = 0 %, 1.0 = 100 %)",
    )

    @field_validator("reduction_percentage")
    @classmethod
    def pct_must_be_valid(cls, v: float) -> float:
        if not (0.0 <= v <= 1.0):
            raise ValueError(
                f"reduction_percentage must be between 0.0 and 1.0, got {v}"
            )
        return v


# ---------------------------------------------------------------------------
# Category → row model + expected headers mapping
# ---------------------------------------------------------------------------

_ROW_MODEL: dict[str, type[BaseModel]] = {
    "footprint": InstitutionalFootprintRow,
    "population": PopulationProjectionRow,
    "scenarios": UnitScenarioRow,
}

_EXPECTED_HEADERS: dict[str, set[str]] = {
    "footprint": {"year", "category", "co2"},
    "population": {"year", "pop"},
    "scenarios": {"scenario", "year", "reduction_percentage"},
}


# ---------------------------------------------------------------------------
# Reduction-objective handler system (mirrors BaseFactorHandler pattern)
# ---------------------------------------------------------------------------


class ReductionObjectiveType(IntEnum):
    """Maps to reduction_objective_type_id sent from frontend (0, 1, 2)."""

    FOOTPRINT = 0  # institutional_footprint
    POPULATION = 1  # population_projections
    SCENARIOS = 2  # unit_scenarios


REDUCTION_OBJECTIVE_HANDLERS: Dict[
    "ReductionObjectiveType", "BaseReductionObjectiveHandler"
] = {}


class ReductionObjectiveHandlerMeta(type):
    """Auto-registers subclasses by their ``objective_type``."""

    def __new__(mcs, name, bases, namespace):
        cls = super().__new__(mcs, name, bases, namespace)
        if name != "BaseReductionObjectiveHandler" and bases:
            obj_type = getattr(cls, "objective_type", None)
            if obj_type is not None:
                REDUCTION_OBJECTIVE_HANDLERS[obj_type] = cls()
        return cls


class BaseReductionObjectiveHandler(metaclass=ReductionObjectiveHandlerMeta):
    """Base handler for reduction-objective CSV rows."""

    objective_type: Optional[ReductionObjectiveType] = None
    config_key: str = ""  # key inside year_config.reduction_objectives
    create_dto: Type[BaseModel]

    @classmethod
    def get_by_type(
        cls, objective_type: ReductionObjectiveType
    ) -> "BaseReductionObjectiveHandler":
        handler = REDUCTION_OBJECTIVE_HANDLERS.get(objective_type)
        if handler is None:
            raise ValueError(
                f"No handler found for reduction_objective_type={objective_type}"
            )
        return handler

    @property
    def expected_columns(self) -> set[str]:
        return set(self.create_dto.model_fields.keys())

    @property
    def required_columns(self) -> set[str]:
        return {
            name for name, f in self.create_dto.model_fields.items() if f.is_required()
        }

    def validate_create(self, payload: dict) -> BaseModel:
        return self.create_dto.model_validate(payload)


class FootprintHandler(BaseReductionObjectiveHandler):
    objective_type = ReductionObjectiveType.FOOTPRINT
    config_key = "institutional_footprint"
    create_dto = InstitutionalFootprintRow


class PopulationHandler(BaseReductionObjectiveHandler):
    objective_type = ReductionObjectiveType.POPULATION
    config_key = "population_projections"
    create_dto = PopulationProjectionRow


class ScenariosHandler(BaseReductionObjectiveHandler):
    objective_type = ReductionObjectiveType.SCENARIOS
    config_key = "unit_scenarios"
    create_dto = UnitScenarioRow


def validate_reduction_objective_csv(
    content: bytes,
    category: str,
) -> list[dict]:
    """Parse and validate a reduction-objective CSV file.

    Decodes the raw bytes, checks that the header row matches the expected
    columns for the given category, then validates every data row against the
    corresponding Pydantic model.  All row errors are collected before raising
    so the caller receives the full list in a single response.

    Args:
        content: Raw bytes of the uploaded CSV file.
        category: One of ``"footprint"``, ``"population"``, ``"scenarios"``.

    Returns:
        List of validated row dicts (``model.model_dump()`` for each row).

    Raises:
        ValueError: If the category is unknown, the headers are wrong, or any
            row fails validation.  The single argument is a list of
            human-readable error strings.
    """
    if category not in _ROW_MODEL:
        raise ValueError([f"Unknown category: {category!r}"])

    # Decode — try UTF-8-SIG first (strips BOM if present), then plain UTF-8,
    # then fall back to latin-1 for legacy Excel exports.
    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            text = content.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise ValueError(["Unable to decode CSV file. Please save it as UTF-8."])

    reader = csv.DictReader(io.StringIO(text))

    # Validate header presence
    if reader.fieldnames is None:
        raise ValueError(["CSV file appears to be empty (no header row found)."])

    actual_headers = {h.strip() for h in reader.fieldnames}
    expected_headers = _EXPECTED_HEADERS[category]
    missing = expected_headers - actual_headers
    if missing:
        raise ValueError(
            [
                f"Missing required columns: {sorted(missing)}. "
                f"Expected: {sorted(expected_headers)}, "
                f"got: {sorted(actual_headers)}."
            ]
        )

    row_model = _ROW_MODEL[category]
    validated_rows: list[dict] = []
    errors: list[str] = []

    for row_idx, raw_row in enumerate(reader, start=2):  # row 1 = header
        # Strip whitespace from keys and values
        cleaned = {k.strip(): v.strip() for k, v in raw_row.items() if k is not None}
        try:
            validated = row_model.model_validate(cleaned)
            validated_rows.append(validated.model_dump())
        except ValidationError as exc:
            for err in exc.errors():
                field = ".".join(str(loc) for loc in err["loc"])
                msg = err["msg"]
                errors.append(f"Row {row_idx}, field '{field}': {msg}")

    if errors:
        raise ValueError(errors)

    return validated_rows


class ReductionObjectiveGoal(BaseModel):
    """Institutional reduction goal configuration."""

    target_year: int = Field(..., description="Target year for reduction")
    reduction_percentage: float = Field(
        ...,
        ge=0,
        le=1,
        description="Reduction percentage as decimal (e.g., 0.4 for 40%)",
    )
    reference_year: int = Field(
        ..., description="Reference year to calculate reduction from"
    )


class ReductionObjectives(BaseModel):
    """Reduction objectives configuration."""

    files: Dict[
        Literal["institutional_footprint", "population_projections", "unit_scenarios"],
        Optional[FileMetadata],
    ] = Field(
        default_factory=lambda: {  # type: ignore
            "institutional_footprint": None,
            "population_projections": None,
            "unit_scenarios": None,
        },
        description="File metadata for reduction objective references",
    )

    # Parsed CSV data — populated automatically on successful CSV upload.
    institutional_footprint: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description=(
            "Parsed rows from the institutional_footprint CSV "
            "(list of {year, category, co2} dicts)"
        ),
    )
    population_projections: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description=(
            "Parsed rows from the population_projections CSV "
            "(list of {year, pop} dicts)"
        ),
    )
    unit_scenarios: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description=(
            "Parsed rows from the unit_scenarios CSV "
            "(list of {scenario, year, reduction_percentage} dicts)"
        ),
    )

    goals: List[ReductionObjectiveGoal] = Field(
        default_factory=list,
        description="List of institutional reduction goals",
    )


class SyncJobSummary(BaseModel):
    """Summary of the latest sync job for a submodule (read-only, not stored in DB)."""

    job_id: int = Field(..., description="Ingestion job ID")
    module_type_id: Optional[int] = Field(None, description="Module type ID")
    data_entry_type_id: Optional[int] = Field(None, description="Data entry type ID")
    year: Optional[int] = Field(None, description="Reference year")
    ingestion_method: int = Field(..., description="0=api, 1=csv, 2=manual")
    target_type: Optional[int] = Field(None, description="0=data_entries, 1=factors")
    state: Optional[int] = Field(None, description="0=NOT_STARTED..3=FINISHED")
    result: Optional[int] = Field(None, description="0=SUCCESS, 1=WARNING, 2=ERROR")
    status_message: Optional[str] = Field(None, description="Human-readable status")
    meta: Optional[Dict[str, Any]] = Field(None, description="Job metadata")


class SubmoduleConfig(BaseModel):
    """Configuration for a single data entry type (submodule)."""

    enabled: bool = Field(default=True, description="Whether this submodule is enabled")
    threshold: Optional[float] = Field(
        default=None,
        description="Fixed threshold in kgCO2eq (null if not set)",
    )

    @field_validator("threshold")
    @classmethod
    def validate_threshold(cls, v: Optional[float]) -> Optional[float]:
        """Threshold must be >= 0 when set."""
        if v is not None and v < 0:
            raise ValueError("threshold must be >= 0")
        return v


class ModuleConfig(BaseModel):
    """Configuration for a module type."""

    enabled: bool = Field(default=True, description="Whether this module is enabled")
    uncertainty_tag: UncertaintyTag = Field(
        default="medium", description="Uncertainty level for the module"
    )
    submodules: Dict[str, SubmoduleConfig] = Field(
        default_factory=dict,
        description="Configuration for each data entry type under this module",
    )


class YearConfigurationBase(BaseModel):
    """Base schema for year configuration."""

    is_started: bool = Field(
        default=False,
        description="If true, data entry is open for users for this year",
    )
    is_reports_synced: bool = Field(
        default=False,
        description="If true, carbon_reports have been initialized for this year",
    )
    config: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Deep configuration (thresholds, tags, goals) as JSON",
    )


class YearConfigurationCreate(YearConfigurationBase):
    """Schema for creating/updating year configuration."""

    pass


class YearConfigurationUpdate(BaseModel):
    """Schema for partial update of year configuration."""

    is_started: Optional[bool] = None
    is_reports_synced: Optional[bool] = None
    config: Optional[Dict[str, Any]] = None

    @model_validator(mode="after")
    def validate_thresholds(self) -> "YearConfigurationUpdate":
        """Validate threshold values in modules config if provided."""
        if not self.config or "modules" not in self.config:
            return self
        modules = self.config["modules"]
        for module_key, module_val in modules.items():
            if not isinstance(module_val, dict):
                continue
            submodules = module_val.get("submodules", {})
            if not isinstance(submodules, dict):
                continue
            for sub_key, sub_val in submodules.items():
                if not isinstance(sub_val, dict):
                    continue
                threshold = sub_val.get("threshold")
                if threshold is not None and (
                    not isinstance(threshold, (int, float)) or threshold < 0
                ):
                    raise ValueError(
                        f"threshold for module {module_key} / submodule {sub_key} "
                        f"must be a number >= 0 or null, got {threshold}"
                    )
        return self


class YearConfigurationResponse(BaseModel):
    """Schema for year configuration response with enriched submodule data."""

    year: int
    is_started: bool
    is_reports_synced: bool
    config: Dict[str, Any]
    latest_jobs: List[SyncJobSummary] = Field(
        default_factory=list,
        description="All current ingestion jobs for this year",
    )
    updated_at: datetime

    class Config:
        from_attributes = True


class FileUploadResponse(BaseModel):
    """Schema for file upload response."""

    success: bool
    file: FileMetadata
    message: str
