from sqlalchemy import select

# Get all records

query = select(Resource)
result = await db.execute(query)
resources = result.scalars().all()

# Get one record

query = select(Resource).where(Resource.id == resource_id)
result = await db.execute(query)
resource = result.scalar_one_or_none()

# With filters

query = select(Resource).where(Resource.unit_id == "ENAC")
result = await db.execute(query)
resources = result.scalars().all()

# With joins

query = select(Resource).join(User).where(User.email == "test@example.com")
result = await db.execute(query)
resources = result.scalars().all()
