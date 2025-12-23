"""
Script to populate local/dev database with fake Units and Users.
- 10,000 units
- 40,000 users (3-15 per unit, normal distribution)
- Each user has one of three roles
- One user for each admin role
- Bulk insert for performance
"""

import asyncio
import random

from faker import Faker
from sqlalchemy import insert

from app.db import SessionLocal
from app.models.unit import Unit
from app.models.user import User

NUM_UNITS = 10000
NUM_USERS = 40000
USER_ROLES = ["co2.user.std", "co2.user.principal", "co2.user.secondary"]
ADMIN_ROLES = [
    "co2.backoffice.std",
    "co2.backoffice.admin",
    "co2.service.mgr",
]

fake = Faker()


async def main():
    async with SessionLocal() as session:
        # Generate units
        units = []
        unit_user_counts = []
        for i in range(NUM_UNITS):
            name = fake.company()
            units.append(
                {
                    "name": name,
                    "role": "unit",
                    "principal_user_id": None,  # To be filled later
                    "principal_user_name": fake.name(),
                    "principal_user_function": fake.job(),
                    "affiliations": [],
                    "visibility": "private",
                }
            )
            # Normal distribution, clipped to [3, 15]
            count = int(random.normalvariate(8, 3))
            count = max(3, min(15, count))
            unit_user_counts.append(count)
        # Adjust total users to NUM_USERS
        total = sum(unit_user_counts)
        for i in range(NUM_UNITS):
            if total > NUM_USERS:
                diff = min(total - NUM_USERS, unit_user_counts[i] - 3)
                unit_user_counts[i] -= diff
                total -= diff
            elif total < NUM_USERS:
                diff = min(NUM_USERS - total, 15 - unit_user_counts[i])
                unit_user_counts[i] += diff
                total += diff
            if total == NUM_USERS:
                break
        # Bulk insert units
        result = await session.execute(insert(Unit), units)
        print(result)
        await session.commit()
        # TODO inser in user_units table
        # unit_ids = result.inserted_primary_key_rows
        # Generate users
        users = []
        user_idx = 0
        for unit_idx, count in enumerate(unit_user_counts):
            unit_id = unit_idx + 1  # Assuming autoincrement
            for _ in range(count):
                role = random.choice(USER_ROLES)
                email = fake.unique.email()
                user_id = fake.unique.random_int(100000, 999999)
                users.append(
                    {
                        "id": user_id,
                        "email": email,
                        "roles": [{"role": role, "on": {"unit": str(unit_id)}}],
                        "is_active": True,
                        "created_at": fake.date_time_this_decade(),
                        "updated_at": fake.date_time_this_decade(),
                        "last_login": None,
                    }
                )
                user_idx += 1
        # Add admin users
        for role in ADMIN_ROLES:
            email = fake.unique.email()
            user_id = fake.unique.random_int(100000, 999999)
            scope = "global" if role != "co2.backoffice.std" else {"unit": "1"}
            users.append(
                {
                    "id": user_id,
                    "email": email,
                    "roles": [{"role": role, "on": scope}],
                    "is_active": True,
                    "created_at": fake.date_time_this_decade(),
                    "updated_at": fake.date_time_this_decade(),
                    "last_login": None,
                }
            )
        # Bulk insert users
        await session.execute(insert(User), users)
        await session.commit()
        print(f"Inserted {len(units)} units and {len(users)} users.")


if __name__ == "__main__":
    asyncio.run(main())
