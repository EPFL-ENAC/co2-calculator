import csv
import io
from datetime import date
from typing import TypedDict

import httpx

ECB_TIMEOUT_SECONDS = 10
ECB_EXR_URL = "https://data-api.ecb.europa.eu/service/data/EXR/"
ECB_EXR_CACHE_TIMEOUT_HOURS = 8


class ExchangeRateRow(TypedDict):
    TIME_PERIOD: str
    CURRENCY: str
    OBS_VALUE: float


class ExchangeRatesService:
    """Service for fetching and caching exchange rates from the ECB API,
    with support for inverting rates and filtering by currency."""

    _cache: dict[int, list[ExchangeRateRow]] = {}
    _cache_date: date | None = None

    def __init__(self):
        pass

    def get_exchange_rate_to_eur(self, year: int, currency: str) -> float:
        """Get the exchange rate from the specified currency to EUR.

        Args:
            year (int): The year for which to fetch the exchange rate.
            currency (str): The currency code to fetch the exchange rate for.

        Raises:
            ValueError: If no exchange rate data is found for the specified year
              and currency or if there is an error fetching the data.

        Returns:
            float: The exchange rate from the specified currency to EUR.
        """
        return self.get_exchange_rate(year, currency, invert=True)

    def get_exchange_rate(
        self, year: int, currency: str, invert: bool = False
    ) -> float:
        """Get the exchange rate for a specific year and currency,
          optionally inverting it to get the rate from EUR to the specified
          currency instead of the other way around.

        Args:
            year (int): The year for which to fetch the exchange rate.
            currency (str): The currency code to filter by (e.g., "CHF").
            invert (bool, optional): Whether to invert the exchange rate.
              Defaults to False.

        Raises:
            ValueError: If no exchange rate data is found for the specified year
              and currency or if there is an error fetching the data.

        Returns:
            float: The exchange rate for the specified year and currency,
              optionally inverted.
        """
        rates = self.get_exchange_rates(year)
        currency_n = self._normalize_currency(currency)

        filtered_rates = [r for r in rates if r["CURRENCY"] == currency_n]

        if not filtered_rates:
            raise ValueError(
                f"No exchange rate data found for year {year} and currency {currency}"
            )

        rate = filtered_rates[0]["OBS_VALUE"]
        if invert:
            return 1 / rate
        return rate

    def get_exchange_rates(self, year: int) -> list[ExchangeRateRow]:
        """Get exchange rates for a specific year, using caching to avoid
          redundant API calls.

        Args:
            year (int): The year for which to fetch exchange rates.
        Returns:
            list[ExchangeRateRow]: A list containing the exchange rates with keys
            "TIME_PERIOD", "CURRENCY", and "OBS_VALUE".
        Raises:
            ValueError: If no exchange rate data is found for the specified year
              and currency or if there is an error fetching the data.
        """
        if (
            ExchangeRatesService._cache_date is None
            or (date.today() - ExchangeRatesService._cache_date).total_seconds()
            > ECB_EXR_CACHE_TIMEOUT_HOURS * 3600
        ):
            self.clear_cache()
            ExchangeRatesService._cache_date = date.today()

        if year in ExchangeRatesService._cache:
            return ExchangeRatesService._cache[year]

        exchange_rates = self.get_exchange_rates_with_eur(year)
        ExchangeRatesService._cache[year] = exchange_rates
        return exchange_rates

    def get_exchange_rates_with_eur(
        self, year: int, currency: str = "", invert: bool = False
    ) -> list[ExchangeRateRow]:
        """Fetch exchange rates from ECB API for the specified year and currency,
          including EUR as a reference. If invert is True, return the inverse of
          the exchange rates (e.g., EUR to CHF instead of CHF to EUR).

        Args:
            year (int): The year for which to fetch exchange rates.
            currency (str, optional): The currency code to filter by (e.g., "CHF").
              If '', fetches all currencies. Defaults to ''.
            invert (bool, optional): Whether to invert the exchange rates.
              Defaults to False.
        Returns:
            list[ExchangeRateRow]: A list containing the exchange rates with keys
            "TIME_PERIOD", "CURRENCY", and "OBS_VALUE".
        Raises:
            ValueError: If no exchange rate data is found for the specified year
              and currency or if there is an error fetching the data.
        """
        today = date.today()
        current_year = today.year

        if year == current_year:
            # Use monthly frequency and average up to the current month
            frequency = "M"
            start_period = f"{year}-01"
            end_period = today.strftime("%Y-%m")
        else:
            frequency = "A"
            start_period = str(year)
            end_period = str(year)

        currency_n = self._normalize_currency(currency) if currency else ""
        url = f"{ECB_EXR_URL}{frequency}.{currency_n}.EUR.SP00.A"
        params = {
            "startPeriod": start_period,
            "endPeriod": end_period,
            "format": "csvdata",
        }

        # Set a timeout for the request to avoid hanging indefinitely
        try:
            response = httpx.get(url, params=params, timeout=ECB_TIMEOUT_SECONDS)
            response.raise_for_status()
        except httpx.HTTPError as e:
            raise ValueError(
                f"Error fetching exchange rates for year {year}: {e}"
            ) from e

        if "No data found" in response.text or "" == response.text.strip():
            raise ValueError(
                f"No exchange rate data found for year {year} and "
                f"currency {currency if currency else 'ALL'}"
            )

        # Parse CSV into list of dicts (typed)
        reader = csv.DictReader(io.StringIO(response.text))

        data: list[ExchangeRateRow] = []
        for row in reader:
            currency_v = row.get("CURRENCY")
            obs_value_v = row.get("OBS_VALUE")
            time_period_v = row.get("TIME_PERIOD")

            if currency_v is None or obs_value_v is None or time_period_v is None:
                continue  # or raise ValueError("Malformed ECB response")

            data.append(
                ExchangeRateRow(
                    TIME_PERIOD=time_period_v,
                    CURRENCY=currency_v,
                    OBS_VALUE=float(obs_value_v),
                )
            )

        if year == current_year:
            # Average monthly rates into a single representative value per currency
            grouped: dict[str, list[float]] = {}

            for rate in data:
                grouped.setdefault(rate["CURRENCY"], []).append(rate["OBS_VALUE"])

            data = [
                ExchangeRateRow(
                    TIME_PERIOD=str(year),
                    CURRENCY=currency,
                    OBS_VALUE=sum(values) / len(values),
                )
                for currency, values in grouped.items()
            ]

        if invert:
            for rate in data:
                rate["OBS_VALUE"] = 1 / rate["OBS_VALUE"]

        return [
            ExchangeRateRow(
                TIME_PERIOD=rate["TIME_PERIOD"],
                CURRENCY=rate["CURRENCY"],
                OBS_VALUE=rate["OBS_VALUE"],
            )
            for rate in data
        ]

    def _normalize_currency(self, currency: str) -> str:
        """Normalize the currency code to uppercase and strip whitespace."""
        return currency.strip().upper()

    @staticmethod
    def clear_cache():
        """Clear the ECB exchange rate cache."""
        ExchangeRatesService._cache.clear()
        ExchangeRatesService._cache_date = None
