# ADR-003: Use FastAPI for Backend

**Status**: Accepted  
**Date**: 2024-11-25  
**Deciders**: Development Team

## Context

We need a Python web framework for RESTful APIs with async I/O,
automated documentation, type validation, and fast development.
The main contenders were FastAPI and Django + Django REST Framework.

## Decision

Use **FastAPI** as the backend framework.

### Why FastAPI

- Async-native (ASGI/Starlette) for better concurrency
- Automatic OpenAPI docs at `/docs` (EPFL requirement ✅)
- Type safety via Pydantic reduces runtime errors
- Minimal boilerplate compared to Django
- Database agnostic (works with any async ORM)
- One of the fastest Python frameworks available

### Trade-offs

**FastAPI wins on:**

- Performance (async I/O)
- Developer experience (less code)
- API documentation (auto-generated)
- Type safety (Pydantic validation)

**Django wins on:**

- Maturity (2005 vs 2018)
- Built-in admin UI
- Batteries-included ecosystem

We chose performance and modern async patterns over Django's
admin UI, which we can build separately if needed.

## Implementation

**Stack:**

- FastAPI + Uvicorn (ASGI server)
- SQLAlchemy 2.x (async ORM) + Alembic (migrations)
- Pydantic 2.x (validation) + pydantic-settings
- authlib (OAuth2/OIDC) + joserfc (JWT)

_See `backend/pyproject.toml` for current versions._

**Example endpoint:**

```python
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/emissions", tags=["emissions"])

@router.post("/", response_model=EmissionResponse)
async def create_emission(
    data: EmissionCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Calculate and store CO2 emission."""
    emission = await emission_service.calculate(db, data, user)
    return emission
```

## References

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [FastAPI Benchmarks](https://www.techempower.com/benchmarks/)
