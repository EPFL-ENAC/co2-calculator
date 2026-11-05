"""External-cloud reference examples (#2771): spent_amount in EUR × ef.

Rows: back-office doc, "test calculation external_clouds". Factor:
external_clouds_factors.csv, every provider 0.259 kg per EUR. The doc fixes
the exchange rates, so the ECB lookup is patched to them.

External AI is not covered: the docs and the code disagree on the request
buckets and the working days (see the #2771 plan).
"""

from unittest.mock import patch

import pytest

from app.models.data_entry import DataEntryTypeEnum
from app.modules.external_cloud_and_ai import ExternalCloudModuleHandler
from app.services.exchange_rates_service import ExchangeRatesService
from tests.unit.modules.reference_examples import TOLERANCE_KG, compute_kg_co2eq

_DOC_RATES_TO_EUR = {"chf": 1.0672, "usd": 0.8849}


@pytest.mark.parametrize(
    ("service_type", "provider", "spent_amount", "currency", "expected_kg"),
    [
        pytest.param("storage", "AWS", 100, "eur", 25.90, id="AWS-100-eur"),
        pytest.param("compute", "GCP", 500, "eur", 129.50, id="GCP-500-eur"),
        pytest.param("storage", "Azure", 250, "chf", 69.10, id="Azure-250-chf"),
        pytest.param("compute", "OVH", 300, "chf", 82.92, id="OVH-300-chf"),
        pytest.param("storage", "AWS", 1000, "usd", 229.19, id="AWS-1000-usd"),
        pytest.param("compute", "GCP", 150, "eur", 38.85, id="GCP-150-eur"),
    ],
)
def test_external_cloud_reference_example(
    service_type: str,
    provider: str,
    spent_amount: float,
    currency: str,
    expected_kg: float,
) -> None:
    ctx = {
        "service_type": service_type,
        "provider": provider,
        "spent_amount": spent_amount,
        "currency": currency,
    }
    values = {"ef_kg_co2eq_per_currency": 0.259, "currency": "eur"}
    with patch.object(
        ExchangeRatesService,
        "get_exchange_rate_to_eur",
        side_effect=lambda _year, code: _DOC_RATES_TO_EUR[code],
    ):
        kg = compute_kg_co2eq(
            ExternalCloudModuleHandler(),
            DataEntryTypeEnum.external_clouds,
            ctx,
            values,
        )
    assert kg == pytest.approx(expected_kg, abs=TOLERANCE_KG)
