import io
from datetime import date

import pandas as pd
import requests

EXR_CACHE: dict[int, pd.DataFrame] = {}


class ExchangeRatesService:
    """Service for fetching and caching exchange rates from the ECB API,
    with support for inverting rates and filtering by currency."""

    def __init__(self):
        pass

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
              and currency.

        Returns:
            float: The exchange rate for the specified year and currency,
              optionally inverted.
        """
        rates = self.get_exchange_rates(year)
        filtered_rates = rates[rates["CURRENCY"] == currency]
        if filtered_rates.empty:
            raise ValueError(
                f"No exchange rate data found for year {year} and currency {currency}"
            )
        if invert:
            filtered_rates["OBS_VALUE"] = 1 / filtered_rates["OBS_VALUE"]
        return filtered_rates["OBS_VALUE"].iloc[0]

    def get_exchange_rates(self, year: int) -> pd.DataFrame:
        """Get exchange rates for a specific year, using caching to avoid
          redundant API calls.

        Args:
            year (int): The year for which to fetch exchange rates.
        Returns:
            pd.DataFrame: A DataFrame containing the exchange rates with columns
            "TIME_PERIOD", "CURRENCY", and "OBS_VALUE".
        Raises:
            ValueError: If no exchange rate data is found for the specified year.
        """
        if year in EXR_CACHE:
            return EXR_CACHE[year]

        exchange_rates = self.get_exchange_rates_with_eur(year)
        EXR_CACHE[year] = exchange_rates
        return exchange_rates

    def get_exchange_rates_with_eur(
        self, year: int, currency: str = "", invert: bool = False
    ) -> pd.DataFrame:
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
            pd.DataFrame: A DataFrame containing the exchange rates with columns
            "TIME_PERIOD", "CURRENCY", and "OBS_VALUE".
        Raises:
            ValueError: If no exchange rate data is found for the specified year
              and currency.
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

        ecb_exr_url = "https://data-api.ecb.europa.eu/service/data/EXR/"
        url = f"{ecb_exr_url}{frequency}.{currency if currency else ''}.EUR.SP00.A"
        params = {
            "startPeriod": start_period,
            "endPeriod": end_period,
            "format": "csvdata",
        }

        response = requests.get(url, params=params)
        response.raise_for_status()

        if "No data found" in response.text or "" == response.text.strip():
            raise ValueError(
                f"No exchange rate data found for year {year} and "
                f"currency {currency if currency else 'ALL'}"
            )

        df = pd.read_csv(io.StringIO(response.text))

        if year == current_year:
            # Average monthly rates into a single representative value per currency
            df = df.groupby("CURRENCY", as_index=False).agg(
                OBS_VALUE=("OBS_VALUE", "mean")
            )
            df.insert(0, "TIME_PERIOD", str(year))

        if invert:
            df["OBS_VALUE"] = 1 / df["OBS_VALUE"]

        return df[["TIME_PERIOD", "CURRENCY", "OBS_VALUE"]]
