from sqlalchemy.sql.elements import ColumnElement
from sqlmodel import case, func

from app.models.data_entry import DataEntry, DataEntryTypeEnum
from app.models.data_entry_emission import DataEntryEmission, EmissionComputation
from app.models.factor import Factor
from app.models.module_type import ModuleTypeEnum
from app.modules.external_cloud_and_ai.data_entries import (
    REQUESTS_FREQUENCY_MAP,
    ExternalAIHandlerCreate,
    ExternalAIHandlerResponse,
    ExternalAIHandlerUpdate,
    ExternalCloudHandlerCreate,
    ExternalCloudHandlerResponse,
    ExternalCloudHandlerUpdate,
)
from app.schemas.data_entry import (
    BaseModuleHandler,
    DataEntryCreate,
    DataEntryUpdate,
)
from app.services.exchange_rates_service import ExchangeRatesService


class ExternalCloudModuleHandler(BaseModuleHandler):
    module_type: ModuleTypeEnum = ModuleTypeEnum.external_cloud_and_ai
    data_entry_type: DataEntryTypeEnum = DataEntryTypeEnum.external_clouds
    create_dto = ExternalCloudHandlerCreate
    update_dto = ExternalCloudHandlerUpdate
    response_dto = ExternalCloudHandlerResponse

    kind_field: str = "provider"
    subkind_field: str = "service_type"

    sort_map = {
        "id": DataEntry.id,
        "service_type": Factor.classification[subkind_field].as_string(),
        "provider": Factor.classification[kind_field].as_string(),
        "spent_amount": DataEntry.data["spent_amount"].as_float(),
        "kg_co2eq": DataEntryEmission.kg_co2eq,
    }

    filter_map = {
        # Factor value when matched, entry data otherwise — search must find
        # the same value the row displays (see to_response's fallbacks).
        "service_type": func.coalesce(
            Factor.classification[subkind_field].as_string(),
            DataEntry.data["service_type"].as_string(),
        ),
        "provider": func.coalesce(
            Factor.classification[kind_field].as_string(),
            DataEntry.data["provider"].as_string(),
        ),
    }

    def to_response(
        self,
        data_entry: DataEntry,
        enriched_data: dict | None = None,
    ) -> ExternalCloudHandlerResponse:
        data = enriched_data if enriched_data is not None else data_entry.data
        primary_factor = data.get("primary_factor", {})
        return self.response_dto.model_validate(
            {
                "id": data_entry.id,
                "data_entry_type_id": data_entry.data_entry_type_id,
                "carbon_report_module_id": data_entry.carbon_report_module_id,
                "source": data_entry.source,
                **data,
                "service_type": primary_factor.get("subkind")
                or data.get("service_type"),
                "provider": primary_factor.get("kind") or data.get("provider"),
            }
        )

    def validate_create(self, payload: dict) -> ExternalCloudHandlerCreate:
        return self.create_dto.model_validate(payload)

    def validate_update(self, payload: dict) -> ExternalCloudHandlerUpdate:
        return self.update_dto.model_validate(payload)

    def resolve_computations(self, data_entry, emission_type, ctx: dict) -> list:

        factor_id = ctx.get("primary_factor_id")
        if factor_id is None:
            return []

        def _cloud_formula(ctx: dict, factor_values: dict) -> float | None:
            # Get the year to ensure we get the correct exchange rate for the year
            # of the purchase
            year = ctx.get("_year")
            if year is None:
                return None

            spent_amount = ctx.get("spent_amount")
            entry_currency = (ctx.get("currency", "") or "eur").lower()
            ef = factor_values.get("ef_kg_co2eq_per_currency")
            ef_currency = (factor_values.get("currency", "eur") or "eur").lower()
            if spent_amount is None or ef is None:
                return None

            spent_amount_eur = spent_amount
            if entry_currency != "eur":
                exchange_rate = ExchangeRatesService().get_exchange_rate_to_eur(
                    year, entry_currency
                )
                spent_amount_eur = spent_amount * exchange_rate
            ef_eur = ef
            if ef_currency != "eur":
                exchange_rate = ExchangeRatesService().get_exchange_rate_to_eur(
                    year, ef_currency
                )
                ef_eur = ef * exchange_rate

            return spent_amount_eur * ef_eur

        return [
            EmissionComputation(
                emission_type=emission_type,
                factor_id=factor_id,
                formula_func=_cloud_formula,
            )
        ]


def _requests_frequency_sort_expr() -> ColumnElement[int]:
    """Return a SQLAlchemy CASE expression mapping frequency strings to ordinals."""
    freq_col = DataEntry.data["requests_per_user_per_day"].as_string()
    return case(
        (freq_col == "1_5", 1),
        (freq_col == "5_20", 2),
        (freq_col == "20_100", 3),
        (freq_col == "gt_100", 4),
        else_=0,
    )


class ExternalAIModuleHandler(BaseModuleHandler):
    module_type: ModuleTypeEnum = ModuleTypeEnum.external_cloud_and_ai
    data_entry_type: DataEntryTypeEnum = DataEntryTypeEnum.external_ai
    create_dto = ExternalAIHandlerCreate
    update_dto = ExternalAIHandlerUpdate
    response_dto = ExternalAIHandlerResponse

    kind_field: str = "provider"
    subkind_field: str = "usage_type"
    sort_map = {
        "id": DataEntry.id,
        "provider": func.coalesce(
            Factor.classification["provider"].as_string(),
            DataEntry.data["provider"].as_string(),
        ),
        "usage_type": func.coalesce(
            Factor.classification["usage_type"].as_string(),
            DataEntry.data["usage_type"].as_string(),
        ),
        "requests_per_user_per_day": _requests_frequency_sort_expr(),
        "fte_count": DataEntry.data["fte_count"].as_float(),
        "kg_co2eq": DataEntryEmission.kg_co2eq,
    }

    filter_map = {
        "provider": func.coalesce(
            Factor.classification["provider"].as_string(),
            DataEntry.data["provider"].as_string(),
        ),
        "usage_type": func.coalesce(
            Factor.classification["usage_type"].as_string(),
            DataEntry.data["usage_type"].as_string(),
        ),
    }

    def to_response(
        self,
        data_entry: DataEntry,
        enriched_data: dict | None = None,
    ) -> ExternalAIHandlerResponse:
        data = enriched_data if enriched_data is not None else data_entry.data
        primary_factor = data.get("primary_factor", {})
        return self.response_dto.model_validate(
            {
                "id": data_entry.id,
                "data_entry_type_id": data_entry.data_entry_type_id,
                "carbon_report_module_id": data_entry.carbon_report_module_id,
                "source": data_entry.source,
                **data,
                "provider": primary_factor.get("provider") or data.get("provider"),
                "usage_type": primary_factor.get("usage_type")
                or data.get("usage_type"),
            }
        )

    def validate_create(self, payload: dict) -> DataEntryCreate:
        return self.create_dto.model_validate(payload)

    def validate_update(self, payload: dict) -> DataEntryUpdate:
        return self.update_dto.model_validate(payload)

    def resolve_computations(self, data_entry, emission_type, ctx: dict) -> list:

        factor_id = ctx.get("primary_factor_id")
        if factor_id is None:
            return []

        def _ai_formula(ctx: dict, factor_values: dict):
            frequency_str = ctx.get("requests_per_user_per_day")
            frequency = REQUESTS_FREQUENCY_MAP.get(frequency_str or "")
            if frequency is None:
                return None
            fte_count = ctx.get("fte_count")
            if fte_count is None:
                return None
            factor_g = factor_values.get("ef_kg_co2eq_per_request")
            if factor_g is None:
                return None
            return (frequency * 5 * 46 * fte_count * factor_g) / 1000

        return [
            EmissionComputation(
                emission_type=emission_type,
                factor_id=factor_id,
                formula_func=_ai_formula,
            )
        ]
