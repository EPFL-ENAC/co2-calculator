"""#2689 -- ``get_current_user`` must hand its pooled connection back before
the route body runs.

``get_db`` is a ``yield`` dependency that FastAPI releases only after the
response is fully sent, and the user lookup autobegins a transaction. Until
this fix every authenticated request pinned one connection from auth to the
last byte -- minutes for an SSE stream or an S3 upload -- and on 2026-09-08
those pins queued behind the DBaaS PgBouncer until nothing could get a
connection at all. #2654 patched the two streams with a second dependency;
this makes the one dependency behave, for every route.
"""

from datetime import timedelta

import pytest
from sqlalchemy import inspect as sa_inspect
from sqlmodel import text

from app.core.security import create_access_token, get_current_user
from app.models.user import User, UserProvider


def _token_for(user: User) -> str:
    return create_access_token(
        data={
            "sub": user.institutional_id,
            "type": "access",
            "email": user.email,
            "institutional_id": user.institutional_id,
            "provider": str(user.provider.value),
        },
        expires_delta=timedelta(minutes=5),
    )


@pytest.mark.asyncio
async def test_get_current_user_returns_detached_user_and_releases_connection(
    db_session,
):
    user = User(
        institutional_id="123456",
        provider=UserProvider.TEST,
        email="pool-release@example.org",
    )
    db_session.add(user)
    await db_session.commit()

    current = await get_current_user(db=db_session, token=_token_for(user))

    assert current.id == user.id
    assert current.institutional_id == "123456"
    # Detached: the object outlives the session's transaction untouched.
    assert sa_inspect(current).detached
    # Released: no transaction open, so the pool got its connection back.
    assert not db_session.in_transaction()
    # The route's own session is still usable afterwards.
    assert (await db_session.execute(text("SELECT 1"))).scalar() == 1
