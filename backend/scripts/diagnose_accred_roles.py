#!/usr/bin/env python3
"""Replay the Accred → Role mapping for one person and show WHY each
authorization is kept or dropped (#2531).

The mapping loop in ``AccredRoleProvider.get_roles_by_user_id`` has five
silent ``continue`` paths. If every authorization hits one, the provider
returns ``[]`` and ``RoleSyncService`` wipes the user's stored roles —
which is the suspected cause of the 403 wave. This script makes that
decision visible per authorization instead of inferring it from logs.

Read-only: one GET to the same Accred endpoint the app already calls on
every login, with the credentials already in ``backend/.env``.

Usage::

    uv run python -m scripts.diagnose_accred_roles 352707
    uv run python -m scripts.diagnose_accred_roles 352707 --raw
"""

import argparse
import asyncio
import sys

import httpx

from app.core.config import get_settings
from app.models.user import RoleName

settings = get_settings()
VALID_ROLES = {role.value for role in RoleName.__members__.values()}
PREFIX = "calco2."


def verdict(auth: dict) -> tuple[str, str]:
    """Mirror the provider's mapping loop, returning (status, reason).

    Kept deliberately in the same order as
    ``AccredRoleProvider.get_roles_by_user_id`` so a divergence here is a
    divergence there.
    """
    name = auth.get("name", "")
    if not name.startswith(PREFIX):
        return "DROP", f"name {name!r} does not start with {PREFIX!r}"
    if name not in VALID_ROLES:
        return "DROP", f"name {name!r} is not a RoleName value"
    if auth.get("state") != "active":
        return "DROP", f"state is {auth.get('state')!r}, not 'active'"
    if not auth.get("accredunitid"):
        return "DROP", "missing 'accredunitid'"
    resource = (auth.get("reason") or {}).get("resource") or {}
    if not (resource.get("cf") or resource.get("altname")):
        return (
            "DROP",
            f"missing resource.cf AND resource.altname (keys: {sorted(resource)})",
        )
    return "KEEP", f"unit {resource.get('cf') or resource.get('altname')}"


async def fetch(person_id: str) -> dict:
    url = f"{settings.ACCRED_API_BASE_URL}/authorizations"
    params = {
        "persid": person_id,
        "state": "active",
        "expand": "0",
        "type": "right",
        "searchauthorization": PREFIX,
    }
    async with httpx.AsyncClient() as client:
        response = await client.get(
            url,
            params=params,
            auth=(settings.ACCRED_API_USERNAME or "", settings.ACCRED_API_KEY or ""),
            timeout=20.0,
        )
        response.raise_for_status()
        return response.json()


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("person_id", help="sciper / Accred persid")
    parser.add_argument("--raw", action="store_true", help="dump the raw payload")
    args = parser.parse_args()

    if not settings.ACCRED_API_BASE_URL or not settings.ACCRED_API_KEY:
        raise SystemExit("Accred not configured in backend/.env")

    data = await fetch(args.person_id)
    authorizations = data.get("authorizations", [])
    print(f"persid={args.person_id}  total_authorizations={len(authorizations)}")

    if args.raw:
        import json

        print(json.dumps(data, indent=2)[:4000])

    kept = 0
    for auth in authorizations:
        status, reason = verdict(auth)
        kept += status == "KEEP"
        print(f"  [{status}] {auth.get('name', '?'):32} {reason}")

    print(f"\nmapped roles: {kept} of {len(authorizations)}")
    if authorizations and kept == 0:
        print(
            "\n>>> THIS USER WOULD BE WIPED: authorizations exist but none map.\n"
            ">>> Hypothesis C confirmed for this person (#2531)."
        )
    elif not authorizations:
        print(
            "\n>>> Accred returned NOTHING for this persid — hypothesis A or B\n"
            ">>> (transient empty, or the app queried the wrong id)."
        )
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
