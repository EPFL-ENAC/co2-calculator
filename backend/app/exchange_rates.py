from app.services.exchange_rates_service import ExchangeRatesService


def main() -> None:
    year = int(input("Enter the year for which you want to fetch exchange rates: "))
    currency = input("Enter the currency code (optional): ") or None
    invert = input("Invert exchange rates? (y/n): ").lower() == "y"
    exchange_rates = ExchangeRatesService().get_exchange_rates_with_eur(
        year, currency or "", invert
    )
    print(exchange_rates)


if __name__ == "__main__":
    main()
