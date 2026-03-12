"""Unit tests for ExchangeRatesService."""

from unittest.mock import patch

import pandas as pd
import pytest

from app.services.exchange_rates_service import ExchangeRatesService


def make_df(
    currency: str = "CHF", obs_value: float = 1.05, year: int = 2024
) -> pd.DataFrame:
    return pd.DataFrame(
        {"TIME_PERIOD": [str(year)], "CURRENCY": [currency], "OBS_VALUE": [obs_value]}
    )


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
        df = make_df("CHF", 1.05)
        with patch.object(service, "get_exchange_rates_with_eur", return_value=df):
            service.get_exchange_rates(2024)
        assert 2024 in ExchangeRatesService._cache

    def test_returns_cached_value_on_second_call(self):
        service = ExchangeRatesService()
        df = make_df("CHF", 1.05)
        with patch.object(
            service, "get_exchange_rates_with_eur", return_value=df
        ) as mock_fetch:
            service.get_exchange_rates(2024)
            service.get_exchange_rates(2024)
        mock_fetch.assert_called_once()

    def test_fetches_separately_for_different_years(self):
        service = ExchangeRatesService()
        df_2023 = make_df("CHF", 1.0, 2023)
        df_2024 = make_df("CHF", 1.05, 2024)
        with patch.object(
            service,
            "get_exchange_rates_with_eur",
            side_effect=[df_2023, df_2024],
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
        df = pd.DataFrame(
            {
                "TIME_PERIOD": ["2024", "2024"],
                "CURRENCY": ["CHF", "USD"],
                "OBS_VALUE": [1.05, 1.08],
            }
        )
        with patch.object(service, "get_exchange_rates_with_eur", return_value=df):
            rate = service.get_exchange_rate(2024, "CHF")
        assert rate == pytest.approx(1.05)

    def test_invert_returns_reciprocal(self):
        service = ExchangeRatesService()
        df = make_df("CHF", 2.0)
        with patch.object(service, "get_exchange_rates_with_eur", return_value=df):
            rate = service.get_exchange_rate(2024, "CHF", invert=True)
        assert rate == pytest.approx(0.5)

    def test_raises_value_error_for_unknown_currency(self):
        service = ExchangeRatesService()
        df = make_df("CHF", 1.05)
        with patch.object(service, "get_exchange_rates_with_eur", return_value=df):
            with pytest.raises(ValueError, match="No exchange rate data found"):
                service.get_exchange_rate(2024, "JPY")

    def test_raises_value_error_with_correct_year_and_currency(self):
        service = ExchangeRatesService()
        df = make_df("CHF", 1.05)
        with patch.object(service, "get_exchange_rates_with_eur", return_value=df):
            with pytest.raises(ValueError, match="2024") as exc_info:
                service.get_exchange_rate(2024, "USD")
        assert "USD" in str(exc_info.value)
