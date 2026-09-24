r"""Time the PgBouncer ``query_wait_timeout`` behind a DB_URL (#2689).

Gate for openshift-app-config#60: once the fleet may exceed the bouncer's
server pool on a burst, a queued request holds its pod pool slot for the
whole wait, so the wait has to be short (~10 s), not the default 120 s.
``app`` has no admin console, so ``SHOW CONFIG`` is out; this measures it.

Transaction pooling hands a server slot back after every transaction, so
``SELECT 1`` on autocommit (what ``probe_pgbouncer_pool`` does) no longer
holds one. Each holder here opens a transaction and leaves it open.
Holders are added one at a time until one is not served within
``--fill-wait`` seconds (default 8, past ``reserve_pool_timeout`` so the
reserve pool is full too). That holder is the queued client, and the
seconds until the bouncer kills it with ``query_wait_timeout`` is the
answer.

While it runs every other client of that pool is queued. ``--give-up``
(default 20 s) closes everything if the bouncer has not answered by then:
the gate is simply not met (the timeout is longer), and the environment
was blocked for fill time + 20 s. Never run this on prod during hours.

Usage, from ``backend/``::

    DB_URL=postgresql://app:...@host:5432/app \\
        uv run python -m scripts.probe_pgbouncer_wait_timeout
"""

import argparse
import asyncio
import os
import time

import psycopg

GATE_SECONDS = 15.0


def _dsn() -> str:
    url = os.environ.get("DB_URL")
    if not url:
        raise SystemExit("DB_URL is not set (postgresql://user:pw@host:5432/db)")
    return url.replace("postgresql+psycopg://", "postgresql://")


class Queued:
    """The first holder the bouncer did not serve, with its pending query."""

    def __init__(
        self, conn: psycopg.AsyncConnection, task: asyncio.Task, started: float
    ):
        self.conn = conn
        self.task = task
        self.started = started


async def _fill(
    dsn: str, wait: float, limit: int
) -> tuple[list[psycopg.AsyncConnection], Queued]:
    """Open holders, each inside an open transaction, until one is queued."""
    holders: list[psycopg.AsyncConnection] = []
    for n in range(1, limit + 1):
        try:
            conn = await psycopg.AsyncConnection.connect(dsn, connect_timeout=10)
        except psycopg.OperationalError as e:
            raise SystemExit(
                f"holder {n}: Postgres refused the login before the bouncer queued "
                f"({str(e).strip().splitlines()[-1]}); the bouncer pool exceeds "
                "max_connections, fix that first"
            ) from e
        started = time.monotonic()
        task = asyncio.ensure_future(conn.execute("select 1"))
        done, _ = await asyncio.wait({task}, timeout=wait)
        if not done:
            print(f"  holder {n:3d}: QUEUED after {wait:.0f}s, timing it")
            return holders, Queued(conn, task, started)
        task.result()
        holders.append(conn)
        print(f"  holder {n:3d}: served")
    raise SystemExit(
        f"{limit} holders served, none queued: raise --max or no bouncer here"
    )


async def _time_out(queued: Queued, give_up: float) -> float | None:
    """Seconds until the bouncer killed the queued query, None past give_up."""
    done, _ = await asyncio.wait({queued.task}, timeout=give_up)
    if not done:
        return None
    try:
        queued.task.result()
    except psycopg.Error as e:
        if "query_wait_timeout" in str(e):
            return time.monotonic() - queued.started
        raise
    raise SystemExit(
        f"queued holder was served after {time.monotonic() - queued.started:.1f}s: "
        "a slot freed up (reserve pool or another client left); rerun"
    )


async def _close_all(conns: list[psycopg.AsyncConnection]) -> None:
    for c in conns:
        try:
            await asyncio.wait_for(c.close(), 2)
        except TimeoutError, psycopg.Error:
            pass


def _verdict(elapsed: float | None, give_up: float) -> str:
    if elapsed is None:
        return (
            f"=> no answer within {give_up:.0f}s: query_wait_timeout > "
            f"{give_up:.0f} s, openshift-app-config#60 gate NOT met"
        )
    gate = "met" if elapsed <= GATE_SECONDS else "NOT met"
    return (
        f"=> query_wait_timeout ~ {elapsed:.1f} s: openshift-app-config#60 "
        f"gate {gate} (<= {GATE_SECONDS:.0f} s)"
    )


async def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument(
        "--fill-wait",
        type=float,
        default=8.0,
        help="seconds a holder may wait to be served",
    )
    ap.add_argument(
        "--give-up",
        type=float,
        default=20.0,
        help="seconds to wait for the bouncer's timeout",
    )
    ap.add_argument("--max", type=int, default=120, help="stop after this many holders")
    args = ap.parse_args()
    dsn = _dsn()
    holders, queued = await _fill(dsn, args.fill_wait, args.max)
    try:
        elapsed = await _time_out(queued, args.give_up)
    finally:
        queued.task.cancel()
        await _close_all([*holders, queued.conn])
    print(f"pool held with {len(holders)} open transactions")
    print(_verdict(elapsed, args.give_up))


if __name__ == "__main__":
    asyncio.run(main())
