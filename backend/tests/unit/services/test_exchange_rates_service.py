"""Unit tests for ExchangeRatesService."""

from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.services.exchange_rates_service import (
    ExchangeRatesService,
)


def make_data(currency: str = "CHF", obs_value: float = 1.05, year: int = 2024):
    return [
        {
            "TIME_PERIOD": str(year),
            "CURRENCY": currency,
            "OBS_VALUE": obs_value,
        }
    ]


def _mock_response(text: str, status_code: int = 200) -> MagicMock:
    """Create a mock httpx.Response with the given text and status code."""
    resp = MagicMock(spec=httpx.Response)
    resp.text = text
    resp.status_code = status_code
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "error", request=MagicMock(), response=resp
        )
    return resp


# --- CSV helpers ---
_CSV_HEADER = "TIME_PERIOD,CURRENCY,OBS_VALUE"


def _csv_annual(currency: str = "CHF", value: float = 1.05, year: int = 2024) -> str:
    return f"{_CSV_HEADER}\n{year},{currency},{value}"


def _csv_monthly(
    currency: str = "CHF", values: list[float] | None = None, year: int | None = None
) -> str:
    if year is None:
        year = date.today().year
    if values is None:
        values = [1.05, 1.06, 1.07]
    lines = [_CSV_HEADER]
    for i, v in enumerate(values, start=1):
        lines.append(f"{year}-{i:02d},{currency},{v}")
    return "\n".join(lines)


@pytest.fixture(autouse=True)
def clear_cache():
    """Clear the ECB exchange rate cache before each test."""
    ExchangeRatesService.clear_cache()
    yield
    ExchangeRatesService.clear_cache()


class TestGetExchangeRates:
    """Tests for get_exchange_rates — cache behaviour."""

    def test_populates_cache_on_first_call(self):
        service = ExchangeRatesService()
        data = make_data("CHF", 1.05)

        with patch.object(service, "get_exchange_rates_with_eur", return_value=data):
            service.get_exchange_rates(2024)

        assert 2024 in ExchangeRatesService._cache

    def test_returns_cached_value_on_second_call(self):
        service = ExchangeRatesService()
        data = make_data("CHF", 1.05)

        with patch.object(
            service, "get_exchange_rates_with_eur", return_value=data
        ) as mock_fetch:
            service.get_exchange_rates(2024)
            service.get_exchange_rates(2024)

        mock_fetch.assert_called_once()

    def test_fetches_separately_for_different_years(self):
        service = ExchangeRatesService()
        data_2023 = make_data("CHF", 1.0, 2023)
        data_2024 = make_data("CHF", 1.05, 2024)

        with patch.object(
            service,
            "get_exchange_rates_with_eur",
            side_effect=[data_2023, data_2024],
        ) as mock_fetch:
            service.get_exchange_rates(2023)
            service.get_exchange_rates(2024)

        assert mock_fetch.call_count == 2
        assert (
            2023 in ExchangeRatesService._cache and 2024 in ExchangeRatesService._cache
        )


class TestGetExchangeRate:
    """Tests for get_exchange_rate — single value retrieval."""

    def test_returns_correct_rate_for_currency(self):
        service = ExchangeRatesService()
        data = [
            {"TIME_PERIOD": "2024", "CURRENCY": "CHF", "OBS_VALUE": 1.05},
            {"TIME_PERIOD": "2024", "CURRENCY": "USD", "OBS_VALUE": 1.08},
        ]

        with patch.object(service, "get_exchange_rates_with_eur", return_value=data):
            rate = service.get_exchange_rate(2024, "CHF")

        assert rate == pytest.approx(1.05)

    def test_invert_returns_reciprocal(self):
        service = ExchangeRatesService()
        data = make_data("CHF", 2.0)

        with patch.object(service, "get_exchange_rates_with_eur", return_value=data):
            rate = service.get_exchange_rate(2024, "CHF", invert=True)

        assert rate == pytest.approx(0.5)

    def test_raises_value_error_for_unknown_currency(self):
        service = ExchangeRatesService()
        data = make_data("CHF", 1.05)

        with patch.object(service, "get_exchange_rates_with_eur", return_value=data):
            with pytest.raises(ValueError, match="No exchange rate data found"):
                service.get_exchange_rate(2024, "JPY")

    def test_raises_value_error_with_correct_year_and_currency(self):
        service = ExchangeRatesService()
        data = make_data("CHF", 1.05)

        with patch.object(service, "get_exchange_rates_with_eur", return_value=data):
            with pytest.raises(ValueError, match="2024") as exc_info:
                service.get_exchange_rate(2024, "USD")

        assert "USD" in str(exc_info.value)


class TestGetExchangeRateToEur:
    """Tests for get_exchange_rate_to_eur — convenience wrapper."""

    def test_delegates_with_invert_true(self):
        service = ExchangeRatesService()
        data = make_data("CHF", 2.0)

        with patch.object(service, "get_exchange_rates_with_eur", return_value=data):
            rate = service.get_exchange_rate_to_eur(2024, "CHF")

        assert rate == pytest.approx(0.5)


class TestGetExchangeRatesWithEur:
    """Tests for get_exchange_rates_with_eur — HTTP fetch + CSV parsing."""

    def test_annual_rate_for_past_year(self):
        service = ExchangeRatesService()
        csv_text = _csv_annual("CHF", 1.05, 2023)

        with patch(
            "app.services.exchange_rates_service.httpx.get",
            return_value=_mock_response(csv_text),
        ):
            result = service.get_exchange_rates_with_eur(2023)

        assert len(result) == 1
        assert result[0]["CURRENCY"] == "CHF"
        assert result[0]["OBS_VALUE"] == pytest.approx(1.05)
        assert result[0]["TIME_PERIOD"] == "2023"

    def test_annual_rate_with_specific_currency(self):
        service = ExchangeRatesService()
        csv_text = _csv_annual("USD", 1.08, 2023)

        with patch(
            "app.services.exchange_rates_service.httpx.get",
            return_value=_mock_response(csv_text),
        ) as mock_get:
            result = service.get_exchange_rates_with_eur(2023, currency="usd")

        assert result[0]["CURRENCY"] == "USD"
        # Verify the URL contains the normalized currency
        call_url = mock_get.call_args[0][0]
        assert ".USD." in call_url

    def test_current_year_averages_monthly_rates(self):
        service = ExchangeRatesService()
        current_year = date.today().year
        csv_text = _csv_monthly("CHF", [1.0, 2.0, 3.0], current_year)

        with patch(
            "app.services.exchange_rates_service.httpx.get",
            return_value=_mock_response(csv_text),
        ):
            result = service.get_exchange_rates_with_eur(current_year)

        assert len(result) == 1
        assert result[0]["CURRENCY"] == "CHF"
        assert result[0]["OBS_VALUE"] == pytest.approx(2.0)
        assert result[0]["TIME_PERIOD"] == str(current_year)

    def test_current_year_averages_multiple_currencies(self):
        service = ExchangeRatesService()
        current_year = date.today().year
        csv_text = (
            f"{_CSV_HEADER}\n"
            f"{current_year}-01,CHF,1.0\n"
            f"{current_year}-02,CHF,3.0\n"
            f"{current_year}-01,USD,1.1\n"
            f"{current_year}-02,USD,1.3"
        )

        with patch(
            "app.services.exchange_rates_service.httpx.get",
            return_value=_mock_response(csv_text),
        ):
            result = service.get_exchange_rates_with_eur(current_year)

        result_by_currency = {r["CURRENCY"]: r for r in result}
        assert result_by_currency["CHF"]["OBS_VALUE"] == pytest.approx(2.0)
        assert result_by_currency["USD"]["OBS_VALUE"] == pytest.approx(1.2)

    def test_invert_returns_reciprocal_rates(self):
        service = ExchangeRatesService()
        csv_text = _csv_annual("CHF", 2.0, 2023)

        with patch(
            "app.services.exchange_rates_service.httpx.get",
            return_value=_mock_response(csv_text),
        ):
            result = service.get_exchange_rates_with_eur(2023, invert=True)

        assert result[0]["OBS_VALUE"] == pytest.approx(0.5)

    def test_http_error_raises_value_error(self):
        service = ExchangeRatesService()

        with patch(
            "app.services.exchange_rates_service.httpx.get",
            return_value=_mock_response("", status_code=500),
        ):
            with pytest.raises(ValueError, match="Error fetching exchange rates"):
                service.get_exchange_rates_with_eur(2023)

    def test_no_data_found_response_raises_value_error(self):
        service = ExchangeRatesService()

        with patch(
            "app.services.exchange_rates_service.httpx.get",
            return_value=_mock_response("No data found for query"),
        ):
            with pytest.raises(ValueError, match="No exchange rate data found"):
                service.get_exchange_rates_with_eur(2023, currency="XYZ")

    def test_empty_response_raises_value_error(self):
        service = ExchangeRatesService()

        with patch(
            "app.services.exchange_rates_service.httpx.get",
            return_value=_mock_response("   "),
        ):
            with pytest.raises(ValueError, match="No exchange rate data found"):
                service.get_exchange_rates_with_eur(2023)

    def test_empty_response_without_currency_shows_all(self):
        service = ExchangeRatesService()

        with patch(
            "app.services.exchange_rates_service.httpx.get",
            return_value=_mock_response("   "),
        ):
            with pytest.raises(ValueError, match="ALL"):
                service.get_exchange_rates_with_eur(2023, currency="")

    def test_malformed_csv_row_is_skipped(self):
        service = ExchangeRatesService()
        # CSV where the OBS_VALUE column is missing entirely from the header,
        # so row.get("OBS_VALUE") returns None and the row is skipped.
        csv_with_missing_column = "TIME_PERIOD,CURRENCY\n2023,CHF"

        with patch(
            "app.services.exchange_rates_service.httpx.get",
            return_value=_mock_response(csv_with_missing_column),
        ):
            result = service.get_exchange_rates_with_eur(2023)

        assert result == []

    def test_csv_row_with_missing_column_is_skipped(self):
        service = ExchangeRatesService()

        # Manually craft a response where a row lacks a key
        csv_with_missing = "TIME_PERIOD,CURRENCY\n2023,CHF"

        with patch(
            "app.services.exchange_rates_service.httpx.get",
            return_value=_mock_response(csv_with_missing),
        ):
            result = service.get_exchange_rates_with_eur(2023)

        # Row is missing OBS_VALUE column entirely → row.get("OBS_VALUE") is None
        assert result == []

    def test_current_year_uses_monthly_frequency_in_url(self):
        service = ExchangeRatesService()
        current_year = date.today().year
        csv_text = _csv_monthly("CHF", [1.05], current_year)

        with patch(
            "app.services.exchange_rates_service.httpx.get",
            return_value=_mock_response(csv_text),
        ) as mock_get:
            service.get_exchange_rates_with_eur(current_year)

        call_url = mock_get.call_args[0][0]
        assert call_url.startswith("https://data-api.ecb.europa.eu/service/data/EXR/M.")

    def test_past_year_uses_annual_frequency_in_url(self):
        service = ExchangeRatesService()
        csv_text = _csv_annual("CHF", 1.05, 2023)

        with patch(
            "app.services.exchange_rates_service.httpx.get",
            return_value=_mock_response(csv_text),
        ) as mock_get:
            service.get_exchange_rates_with_eur(2023)

        call_url = mock_get.call_args[0][0]
        assert call_url.startswith("https://data-api.ecb.europa.eu/service/data/EXR/A.")

    def test_empty_currency_param_produces_empty_segment_in_url(self):
        service = ExchangeRatesService()
        csv_text = _csv_annual("CHF", 1.05, 2023)

        with patch(
            "app.services.exchange_rates_service.httpx.get",
            return_value=_mock_response(csv_text),
        ) as mock_get:
            service.get_exchange_rates_with_eur(2023, currency="")

        call_url = mock_get.call_args[0][0]
        assert "A..EUR" in call_url


class TestCacheExpiration:
    """Tests for cache timeout behaviour."""

    def test_cache_expires_after_timeout(self):
        service = ExchangeRatesService()
        data = make_data("CHF", 1.05)

        with patch.object(
            service, "get_exchange_rates_with_eur", return_value=data
        ) as mock_fetch:
            service.get_exchange_rates(2024)

            # date arithmetic has day granularity, so set the cache date
            # 2 days in the past to guarantee total_seconds() exceeds the
            # timeout threshold (ECB_EXR_CACHE_TIMEOUT_HOURS * 3600).
            ExchangeRatesService._cache_date = date.today() - timedelta(days=2)
            service.get_exchange_rates(2024)

        assert mock_fetch.call_count == 2
