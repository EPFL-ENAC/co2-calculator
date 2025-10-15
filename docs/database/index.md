# Database Overview

This section provides an overview of the database layer, including the technology choices, access patterns, and management strategies.

## Database Technology

- **Engine**: PostgreSQL
- **ORM**: SQLAlchemy
- **Migration Tool**: Alembic
- **Connection Pooling**: Built-in PostgreSQL pooling or PgBouncer
- **Backup Solution**: pg_dump with cloud storage integration

## Key Characteristics

- ACID compliance for data integrity
- JSONB support for flexible data structures
- Advanced indexing capabilities
- Robust transaction support
- Extensive extension ecosystem

## Integration Points

- **Backend Application**: Direct connection through SQLAlchemy
- **Migration System**: Alembic for schema versioning
- **Backup System**: Automated backup scripts
- **Monitoring**: PostgreSQL statistics and custom metrics
- **Admin Tools**: pgAdmin, psql, custom admin interfaces

## Subsystems

- [Schema](./schema.md) - Database schema and entity relationships
- [Data Flows](./data-flows.md) - How data moves through the system
- [Migrations](./migrations.md) - Schema evolution and versioning
- [Maintenance](./maintenance.md) - Backup, recovery, and routine tasks

For architectural overview, see [Architecture Overview](../architecture/index.md).
