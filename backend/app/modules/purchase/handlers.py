from app.models.data_entry import DataEntry, DataEntryTypeEnum
from app.models.data_entry_emission import (
    DataEntryEmission,
    EmissionComputation,
)
from app.models.module_type import ModuleTypeEnum
from app.modules.purchase.data_entries import (
    PurchaseCentralizedHandlerCreate,
    PurchaseCentralizedHandlerResponse,
    PurchaseCentralizedHandlerUpdate,
    PurchaseHandlerCreate,
    PurchaseHandlerResponse,
    PurchaseHandlerUpdate,
)
from app.schemas.data_entry import BaseModuleHandler
from app.services.exchange_rates_service import ExchangeRatesService


class PurchaseModuleHandler(BaseModuleHandler):
    module_type: ModuleTypeEnum = ModuleTypeEnum.purchase
    category_field: str = "purchase_category"
    registration_keys = [
        DataEntryTypeEnum.scientific_equipment,
        DataEntryTypeEnum.it_equipment,
        DataEntryTypeEnum.consumable_accessories,
        DataEntryTypeEnum.biological_chemical_gaseous_product,
        DataEntryTypeEnum.services,
        DataEntryTypeEnum.vehicles,
        DataEntryTypeEnum.other_purchases,
    ]

    create_dto = PurchaseHandlerCreate
    update_dto = PurchaseHandlerUpdate
    response_dto = PurchaseHandlerResponse

    kind_field: str = "purchase_institutional_code"
    # purchase_additional_code is optional on entries but is the primary
    # factor key when present: it overrides the institutional-code match.
    kind_field_override: str | None = "purchase_additional_code"
    subkind_field: str | None = ""
    # Required non-empty on create; update rejects present-but-blank/null
    # (key-absent means "not updating"). CSV omits the key entirely when the
    # cell is empty, so entries can still lack it — matching stays optional.
    require_factor_to_match = False

    sort_map = {
        "id": DataEntry.id,
        "name": DataEntry.data["name"].as_string(),
        "supplier": DataEntry.data["supplier"].as_string(),
        "quantity": DataEntry.data["quantity"].as_float(),
        "total_spent_amount": DataEntry.data["total_spent_amount"].as_float(),
        "currency": DataEntry.data["currency"].as_string(),
        "purchase_institutional_code": DataEntry.data[
            "purchase_institutional_code"
        ].as_string(),
        "kg_co2eq": DataEntryEmission.kg_co2eq,
    }

    filter_map = {
        "name": DataEntry.data["name"].as_string(),
        "supplier": DataEntry.data["supplier"].as_string(),
        "purchase_institutional_code": DataEntry.data[
            "purchase_institutional_code"
        ].as_string(),
    }

    def to_response(
        self,
        data_entry: DataEntry,
        enriched_data: dict | None = None,
    ) -> PurchaseHandlerResponse:
        data = enriched_data if enriched_data is not None else data_entry.data
        return self.response_dto.model_validate(
            {
                "id": data_entry.id,
                **data,
                "data_entry_type_id": data_entry.data_entry_type_id,
                "carbon_report_module_id": data_entry.carbon_report_module_id,
                "name": data.get("name"),
                "supplier": data.get("supplier"),
                "quantity": data.get("quantity"),
                "purchase_institutional_code": data.get("purchase_institutional_code"),
                "total_spent_amount": data.get("total_spent_amount"),
                "kg_co2eq": data.get("kg_co2eq", None),
            }
        )

    def validate_create(self, payload: dict) -> PurchaseHandlerCreate:
        return self.create_dto.model_validate(payload)

    def validate_update(self, payload: dict) -> PurchaseHandlerUpdate:
        return self.update_dto.model_validate(payload)

    def resolve_computations(self, data_entry, emission_type, ctx: dict) -> list:

        factor_id = ctx.get("primary_factor_id")
        if factor_id is None:
            return []

        def _purchase_formula(ctx: dict, factor_values: dict) -> float | None:
            # Get the year to ensure we get the correct exchange rate for the year
            # of the purchase
            year = ctx.get("_year")
            if year is None:
                return None

            total_spent_amount = ctx.get("total_spent_amount")
            if total_spent_amount is None:
                return None
            entry_currency = (ctx.get("currency", "chf") or "chf").lower()
            ef = factor_values.get("ef_kg_co2eq_per_currency")
            if ef is None:
                return None
            ef_currency = (factor_values.get("currency", "eur") or "eur").lower()
            if total_spent_amount is None or ef is None:
                return None

            # Use the exchange rate service to convert the total
            # spent amount to the eur currency
            total_spent_amount_eur = total_spent_amount
            if entry_currency != "eur":
                exchange_rate = ExchangeRatesService().get_exchange_rate_to_eur(
                    year, entry_currency
                )
                total_spent_amount_eur = total_spent_amount * exchange_rate
            # Similarly, convert the emission factor to eur if it's in a different
            # currency, so that the final kg_co2eq is correctly computed in relation
            # to the total spent amount in eur
            ef_eur = ef
            if ef_currency != "eur":
                exchange_rate = ExchangeRatesService().get_exchange_rate_to_eur(
                    year, ef_currency
                )
                ef_eur = ef * exchange_rate

            return total_spent_amount_eur * ef_eur

        return [
            EmissionComputation(
                emission_type=emission_type,
                factor_id=factor_id,
                formula_func=_purchase_formula,
            )
        ]


class PurchaseCentralizedModuleHandler(BaseModuleHandler):
    module_type: ModuleTypeEnum = ModuleTypeEnum.purchase
    data_entry_type: DataEntryTypeEnum = DataEntryTypeEnum.purchases_centralized

    create_dto = PurchaseCentralizedHandlerCreate
    update_dto = PurchaseCentralizedHandlerUpdate
    response_dto = PurchaseCentralizedHandlerResponse

    kind_field: str = "name"
    subkind_field: str | None = ""

    sort_map = {
        "id": DataEntry.id,
        "name": DataEntry.data["name"].as_string(),
        "unit": DataEntry.data["unit"].as_string(),
        "annual_consumption": DataEntry.data["annual_consumption"].as_float(),
        "coef_to_kg": DataEntry.data["coef_to_kg"].as_float(),
        "kg_co2eq": DataEntryEmission.kg_co2eq,
    }

    filter_map = {
        "name": DataEntry.data["name"].as_string(),
        "unit": DataEntry.data["unit"].as_string(),
    }

    def to_response(
        self,
        data_entry: DataEntry,
        enriched_data: dict | None = None,
    ) -> PurchaseCentralizedHandlerResponse:
        data = enriched_data if enriched_data is not None else data_entry.data
        return self.response_dto.model_validate(
            {
                "id": data_entry.id,
                "data_entry_type_id": data_entry.data_entry_type_id,
                "carbon_report_module_id": data_entry.carbon_report_module_id,
                **data,
            }
        )

    def validate_create(self, payload: dict) -> PurchaseCentralizedHandlerCreate:
        return self.create_dto.model_validate(payload)

    def validate_update(self, payload: dict) -> PurchaseCentralizedHandlerUpdate:
        return self.update_dto.model_validate(payload)

    def resolve_computations(self, data_entry, emission_type, ctx: dict) -> list:

        factor_id = ctx.get("primary_factor_id")
        if factor_id is None:
            return []

        def _additional_purchase_formula(ctx: dict, factor_values: dict):
            annual_consumption = ctx.get("annual_consumption")
            if annual_consumption is None:
                return None
            coef_to_kg = ctx.get("coef_to_kg")
            if coef_to_kg is None:
                return None
            ef = factor_values.get("ef_kg_co2eq_per_kg")
            if ef is None:
                return None
            return annual_consumption * coef_to_kg * ef

        return [
            EmissionComputation(
                emission_type=emission_type,
                factor_id=factor_id,
                formula_func=_additional_purchase_formula,
            )
        ]
