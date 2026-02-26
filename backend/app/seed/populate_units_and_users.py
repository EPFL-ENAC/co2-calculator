"""
Ultra-fast PostgreSQL COPY seeder

- 3,000 units
- 10,000 users (3–15 per unit, normal distribution around 8)
- 2 global admin users
- Bulk inserts using asyncpg COPY
- Principal users assigned in SQL
"""

import asyncio
import json
import random

import asyncpg
from faker import Faker

from app.core.config import get_settings
from app.models.user import RoleName, UserProvider

NUM_UNITS = 3000
NUM_USERS = 10000


NUM_UNITS = 300
NUM_USERS = 1000

USER_ROLES = [
    RoleName.CO2_USER_STD,
    RoleName.CO2_USER_PRINCIPAL,
]

ADMIN_ROLES = [
    RoleName.CO2_BACKOFFICE_METIER,
    RoleName.CO2_SUPERADMIN,
]

fake = Faker()


# ============================================================
# DATABASE
# ============================================================


async def get_asyncpg_connection():
    settings = get_settings()
    db_url = settings.DB_URL.replace("postgresql+psycopg", "postgresql")
    return await asyncpg.connect(db_url)


# ============================================================
# UNITS
# ============================================================


def generate_units():
    rows = []

    for i in range(NUM_UNITS):
        provider_code = f"U{i:05d}"

        affiliations = []
        if random.random() < 0.7:
            affiliations.append(random.choice(["SB", "STI", "IC", "SV", "EDOC"]))
        if random.random() < 0.3:
            affiliations.append(random.choice(["ENAC", "INPLUS", "ISIC", "IIE"]))

        cost_centers = [
            f"C{random.randint(1000, 9999)}" for _ in range(random.randint(1, 3))
        ]

        rows.append(
            (
                provider_code,
                fake.company(),
                None,
                json.dumps(cost_centers),
                json.dumps(affiliations),
                UserProvider.DEFAULT.name,
            )
        )

    return rows


async def insert_units(conn, rows):
    await conn.execute("""
        CREATE TEMP TABLE tmp_units (
            provider_code TEXT,
            name TEXT,
            principal_user_institutional_id TEXT,
            cost_centers JSONB,
            affiliations JSONB,
            provider TEXT
        ) ON COMMIT DROP
    """)

    await conn.copy_records_to_table(
        "tmp_units",
        records=rows,
    )

    unit_ids = await conn.fetch("""
        INSERT INTO units (
            provider_code,
            name,
            principal_user_institutional_id,
            cost_centers,
            affiliations,
            provider
        )
        SELECT
            provider_code,
            name,
            principal_user_institutional_id,
            cost_centers,
            affiliations,
            provider::user_provider_enum
        FROM tmp_units
        RETURNING id, provider_code
    """)

    return {r["provider_code"]: r["id"] for r in unit_ids}


# ============================================================
# USERS
# ============================================================


def distribute_users():
    counts = []
    total = 0

    for _ in range(NUM_UNITS):
        c = int(random.normalvariate(8, 3))
        c = max(3, min(15, c))
        counts.append(c)
        total += c

    # normalize to NUM_USERS
    diff = NUM_USERS - total
    i = 0
    while diff != 0:
        if diff > 0 and counts[i] < 15:
            counts[i] += 1
            diff -= 1
        elif diff < 0 and counts[i] > 3:
            counts[i] -= 1
            diff += 1
        i = (i + 1) % NUM_UNITS

    return counts


def generate_users(unit_map):
    user_rows = []
    unit_user_rows = []

    counts = distribute_users()
    user_counter = 0

    unit_codes = list(unit_map.keys())

    for unit_index, count in enumerate(counts):
        unit_code = unit_codes[unit_index]
        unit_id = unit_map[unit_code]

        for _ in range(count):
            provider_code = f"USR{user_counter:06d}"
            user_counter += 1

            role = random.choice(USER_ROLES)

            user_rows.append(
                (
                    provider_code,
                    fake.unique.email(),
                    fake.name(),
                    fake.job(),
                    UserProvider.DEFAULT.name,
                    json.dumps(
                        [
                            {
                                "role": role.value,
                                "on": {"provider_code": unit_code},
                            }
                        ]
                    ),
                    None,
                )
            )

            unit_user_rows.append((provider_code, unit_id, role.name))

    # Admins
    # Admins
    first_unit_code = unit_codes[0]
    first_unit_id = unit_map[first_unit_code]

    for role in ADMIN_ROLES:
        provider_code = f"ADMIN{user_counter:06d}"
        user_counter += 1

        if role == RoleName.CO2_SUPERADMIN:
            roles_raw = [{"role": role.value, "on": {"scope": "global"}}]
        else:
            roles_raw = [
                {
                    "role": role.value,
                    "on": {"affiliation": random.choice(["SB", "STI", "IC", "SV"])},
                }
            ]

        user_rows.append(
            (
                provider_code,
                fake.unique.email(),
                fake.name(),
                fake.job(),
                UserProvider.DEFAULT.name,
                json.dumps(roles_raw),
                None,
            )
        )

        # (attach admin to first unit)
        unit_user_rows.append((provider_code, first_unit_id, role.name))

    return user_rows, unit_user_rows


async def insert_users(conn, user_rows):
    await conn.execute("""
        CREATE TEMP TABLE tmp_users (
            provider_code TEXT,
            email TEXT,
            display_name TEXT,
            function TEXT,
            provider TEXT,
            roles_raw JSONB,
            last_login TIMESTAMPTZ
        ) ON COMMIT DROP
    """)

    await conn.copy_records_to_table(
        "tmp_users",
        records=user_rows,
    )

    users = await conn.fetch("""
        INSERT INTO users (
            provider_code,
            email,
            display_name,
            function,
            provider,
            roles_raw,
            last_login
        )
        SELECT
            provider_code,
            email,
            display_name,
            function,
            provider::user_provider_enum,
            roles_raw,
            last_login
        FROM tmp_users
        RETURNING id, provider_code
    """)

    return {r["provider_code"]: r["id"] for r in users}


async def insert_unit_users(conn, unit_user_rows, user_map):
    records = [
        (unit_id, user_map[pcode], role) for pcode, unit_id, role in unit_user_rows
    ]

    await conn.copy_records_to_table(
        "unit_users",
        records=records,
        columns=["unit_id", "user_id", "role"],
    )


# ============================================================
# PRINCIPAL ASSIGNMENT (SQL SIDE)
# ============================================================


async def assign_principals(conn):
    await conn.execute("""
        UPDATE units u
        SET principal_user_institutional_id = sub.provider_code
        FROM (
            SELECT DISTINCT ON (uu.unit_id)
                uu.unit_id,
                usr.provider_code
            FROM unit_users uu
            JOIN users usr ON usr.id = uu.user_id
            ORDER BY uu.unit_id, random()
        ) sub
        WHERE u.id = sub.unit_id
    """)


# ============================================================
# MAIN
# ============================================================


async def main():
    conn = await get_asyncpg_connection()

    try:
        async with conn.transaction():
            print("Seeding units...")
            unit_rows = generate_units()
            unit_map = await insert_units(conn, unit_rows)
            print(f"✓ Inserted {len(unit_map)} units")

            print("Seeding users...")
            user_rows, unit_user_rows = generate_users(unit_map)
            user_map = await insert_users(conn, user_rows)
            print(f"✓ Inserted {len(user_map)} users")

            print("Creating unit-user relationships...")
            await insert_unit_users(conn, unit_user_rows, user_map)
            print(f"✓ Created {len(unit_user_rows)} relationships")

            print("Assigning principal users...")
            await assign_principals(conn)
            print("✓ Principal users assigned")

        print("\nAll seeding operations completed successfully!\n")

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
