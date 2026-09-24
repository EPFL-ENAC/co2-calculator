r"""Check that the PgBouncer behind ``DB_URL`` replays prepared statements
across server connections (#2689, transaction pooling).

Connection A prepares one statement on its first run (``prepare_threshold``
0) and re-executes it; connection B runs a query in between so that A's
server connection goes back to the bouncer's pool and A gets a different
one next time. With ``max_prepared_statements = 0`` the second server
connection has never seen A's statement and Postgres answers ``prepared
statement "_pg3_0" does not exist``; with a value > 0 (PgBouncer >= 1.22)
the bouncer prepares it there transparently and every round succeeds.

Prints the distinct server pids A landed on. One pid means the bouncer
never rotated A's connection and the run is inconclusive: rerun, or run
two copies at once. Usage, from ``backend/``::

    DB_URL=postgresql://app:...@host:5432/app \\
        uv run python -m scripts.probe_pgbouncer_prepared
"""

import asyncio
import os

import psycopg

ROUNDS = 20
STATEMENT = "select pg_backend_pid(), %s::int"


def _dsn() -> str:
    url = os.environ.get("DB_URL")
    if not url:
        raise SystemExit("DB_URL is not set (postgresql://user:pw@host:5432/db)")
    return url.replace("postgresql+psycopg://", "postgresql://")


async def _round(a: psycopg.AsyncConnection, b: psycopg.AsyncConnection, i: int) -> int:
    cur = await a.execute(STATEMENT, [i])
    row = await cur.fetchone()
    if row is None:
        raise RuntimeError("probe statement returned no row")
    # B's query is what lets the bouncer hand A's server connection away.
    await b.execute("select 1")
    return row[0]


async def main() -> None:
    dsn = _dsn()
    async with (
        await psycopg.AsyncConnection.connect(
            dsn, autocommit=True, prepare_threshold=0
        ) as a,
        await psycopg.AsyncConnection.connect(dsn, autocommit=True) as b,
    ):
        pids = {await _round(a, b, i) for i in range(ROUNDS)}
    print(f"{ROUNDS} prepared executions OK across server pids {sorted(pids)}")
    if len(pids) == 1:
        print("inconclusive: A kept one server connection; rerun or run two copies")
        return
    print("max_prepared_statements > 0: the bouncer replays prepared statements")


if __name__ == "__main__":
    asyncio.run(main())
