r"""Measure the PgBouncer server pool behind a DB_URL by filling it (#2689).

The bouncer's pool is per (user, database), and ``app`` has no admin
console, so ``SHOW POOLS`` is out. What we can do is what the incident did
by accident: open client connections one at a time, each running one
``SELECT 1``, until the bouncer queues us instead of serving us. The pool
is the number of connections it served plus the slots that were already
in use when we started.

PgBouncer 1.22+ says "No server connection available in postgres backend,
client being queued" as a NOTICE the moment it queues; older versions just
hang until ``query_wait_timeout``. Both are handled: a queued probe is one
whose ``SELECT 1`` does not answer within ``--wait`` seconds. A bouncer
whose pool is larger than Postgres itself never queues: Postgres refuses
the login first ("remaining connection slots are reserved"), and that is
reported as the answer too -- the cap is ``max_connections``, not the
bouncer.

The reserve pool (``reserve_pool_size``) only opens for a client that has
waited ``reserve_pool_timeout`` (5 s by default), so a first pass with
``--wait 2`` measures ``default_pool_size`` and ``--wait 8`` measures
``default_pool_size + reserve_pool_size``.

While it runs, every other client of that pool is queued for up to
``--wait`` seconds, then the probe closes everything at once. Run it on
prod off-hours, and never with ``--wait`` above the bouncer's
``query_wait_timeout`` (120 s).

Usage, from ``backend/`` with the environment's URL in ``DB_URL``::

    DB_URL=postgresql://app:...@host:5432/app \\
        uv run python -m scripts.probe_pgbouncer_pool --wait 2
    DB_URL=... uv run python -m scripts.probe_pgbouncer_pool --wait 8
"""

import argparse
import asyncio
import os
import sys
from dataclasses import dataclass, field

import psycopg

QUEUED_NOTICE = "client being queued"

BASELINE_SQL = """
SELECT
    (SELECT client_addr::text FROM pg_stat_activity WHERE pid = pg_backend_pid()),
    count(*) FILTER (WHERE backend_type = 'client backend'),
    count(*) FILTER (
        WHERE backend_type = 'client backend'
          AND client_addr = (
              SELECT client_addr FROM pg_stat_activity WHERE pid = pg_backend_pid()
          )
    )
FROM pg_stat_activity
"""


@dataclass
class Probe:
    conn: psycopg.AsyncConnection
    notices: list[str] = field(default_factory=list)
    latency: float | None = None
    pending: asyncio.Task | None = None


class PostgresRefused(Exception):
    """Postgres, not the bouncer, turned the login away: max_connections."""


def _dsn() -> str:
    url = os.environ.get("DB_URL")
    if not url:
        raise SystemExit("DB_URL is not set (postgresql://user:pw@host:5432/db)")
    return url.replace("postgresql+psycopg://", "postgresql://")


async def _open(dsn: str) -> Probe:
    try:
        conn = await psycopg.AsyncConnection.connect(
            dsn, autocommit=True, connect_timeout=10
        )
    except psycopg.OperationalError as e:
        if any(
            s in str(e)
            for s in ("connection slots", "too many con", "too many clients")
        ):
            raise PostgresRefused(str(e).strip().splitlines()[-1]) from e
        raise
    probe = Probe(conn)
    conn.add_notice_handler(lambda d: probe.notices.append(d.message_primary or ""))
    return probe


async def _served(probe: Probe, wait: float) -> bool:
    """True if the bouncer handed this client a server slot within ``wait``.

    A queued query is left pending, not cancelled: psycopg cancels by
    sending a cancel request to the server, and a client without a server
    slot has nowhere to send it, so ``wait_for`` would hang there for
    ``query_wait_timeout``. The task is dropped with its connection.
    """
    loop = asyncio.get_running_loop()
    start = loop.time()
    task = asyncio.ensure_future(probe.conn.execute("SELECT 1"))
    done, _ = await asyncio.wait({task}, timeout=wait)
    if task not in done:
        probe.pending = task
        return False
    task.result()
    probe.latency = loop.time() - start
    return not any(QUEUED_NOTICE in n for n in probe.notices)


async def _baseline(dsn: str) -> tuple[str | None, int, int]:
    async with await psycopg.AsyncConnection.connect(dsn, autocommit=True) as conn:
        cur = await conn.execute(BASELINE_SQL)
        row = await cur.fetchone()
    if row is None:
        raise SystemExit("pg_stat_activity returned nothing")
    return row[0], row[1], row[2]


async def _close_all(probes: list[Probe]) -> None:
    for p in probes:
        if p.pending is not None and not p.pending.done():
            p.pending.cancel()
        try:
            await asyncio.wait_for(p.conn.close(), 2)
        except Exception:  # noqa: BLE001 -- a queued client may not close cleanly
            pass


async def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--wait", type=float, default=2.0, help="seconds a probe may wait")
    ap.add_argument("--max", type=int, default=120, help="stop after this many probes")
    args = ap.parse_args()
    dsn = _dsn()

    my_addr, all_clients, via_my_addr = await _baseline(dsn)
    print(f"seen by postgres as client_addr={my_addr}")
    print(
        f"client backends before the probe: {all_clients} total, "
        f"{via_my_addr} from that address"
    )

    probes: list[Probe] = []
    queued: Probe | None = None
    refused: str | None = None
    try:
        for n in range(1, args.max + 1):
            try:
                probe = await _open(dsn)
            except PostgresRefused as e:
                refused = str(e)
                print(f"  probe {n:3d}: REFUSED by postgres: {refused}")
                break
            probes.append(probe)
            if await _served(probe, args.wait):
                print(f"  probe {n:3d}: served in {probe.latency:.3f}s", flush=True)
                continue
            queued = probe
            print(f"  probe {n:3d}: QUEUED after {args.wait}s {probe.notices or ''}")
            break
    finally:
        await _close_all(probes)

    served = len(probes) - (1 if queued else 0)
    # ``via_my_addr`` counted the baseline connection itself; it is closed
    # now, so the slots in use during the probe are one fewer.
    in_use = via_my_addr - 1
    print(f"\nserved {served} new connections on top of {in_use} already in use")
    if refused is not None:
        print(
            f"=> no bouncer queue before postgres max_connections: the cap is "
            f"postgres itself, reached at {served + in_use} client backends"
        )
        return 0
    if queued is None:
        print(
            f"=> no queue reached within {args.max} probes: "
            "either no bouncer, or its pool is larger"
        )
        return 1
    print(f"=> pool for this (user, database) at --wait {args.wait}: {served + in_use}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
