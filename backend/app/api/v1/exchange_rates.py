from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_current_user
from app.models.user import User
from app.services.exchange_rates_service import ExchangeRatesService
from app.utils.currencies import SUPPORTED_CURRENCIES

router = APIRouter()


@router.get("/{year}")
def get_exchange_rates_to_eur(
    year: int,
    current_user: User = Depends(get_current_user),
) -> dict[str, float]:
    """Yearly average ECB rates as EUR per unit of each supported currency.

    Sync handler on purpose: the ECB fetch behind the service's cache is
    blocking, so FastAPI must run it in the threadpool.
    """
    try:
        rates = ExchangeRatesService().get_exchange_rates(year)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No exchange rates available for year {year}",
        ) from e
    eur_per_unit: dict[str, float] = {}
    for row in rates:
        code = str(row["CURRENCY"]).lower()
        value = row["OBS_VALUE"]
        if code in SUPPORTED_CURRENCIES and value:
            eur_per_unit[code] = 1 / float(value)
    if not eur_per_unit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No exchange rates available for year {year}",
        )
    return eur_per_unit
