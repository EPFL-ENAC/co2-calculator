# ADR-004: Use PostgreSQL for Production and SQLite for Development

**Status**: ✅ Accepted

## Context

The CO2 Calculator stores user data, emission records, organizational
units, and audit logs with 10-year retention. We need ACID compliance,
concurrent access, complex queries, and FastAPI async compatibility.

New developers should start coding immediately without external service
setup. Production requires robust backups, replication, and EPFL
infrastructure compatibility.

## Decision

Use a dual-database strategy:

- **Production**: PostgreSQL 15+ (EPFL-managed or cloud service)
- **Development**: SQLite with aiosqlite (zero-config local setup)

The application auto-detects from environment variables. If
`DB_URL` or PostgreSQL credentials exist, use PostgreSQL.
Otherwise, default to SQLite for instant local development.

**Why PostgreSQL**: JSONB support for flexible user roles, advanced
indexing, mature backup/replication, and EPFL infrastructure support.

**Why SQLite**: Zero configuration enables developers to run the app
immediately without Docker or external services. CI tests run faster.

Both support SQLAlchemy 2.0 async via psycopg3 and aiosqlite with
identical application code.

**Alternatives rejected**:

- **MySQL**: Weaker JSON support, less advanced data types, inferior
  async library maturity
- **MongoDB**: Inappropriate for relational data (users to units to
  emissions). We need foreign keys, complex joins, and strict ACID
  guarantees for financial-grade accuracy

## Consequences

**Positive**:

- Developers start coding immediately without database setup
- Production gets robust PostgreSQL with native JSONB and replication
- Same SQLAlchemy codebase works across both databases
- CI tests run faster using SQLite
- PostgreSQL backups use pg_dump daily with WAL archiving for 10-year
  retention
- Connection pooling via SQLAlchemy (20 connections) with optional
  PgBouncer for high load

**Negative**:

- Must test on PostgreSQL before production (SQL dialect differences)
- SQLite limited to single writer (local dev only, never production)
- Operational overhead managing PostgreSQL (mitigated by using
  EPFL-managed service or AWS RDS)

**Configuration** uses Pydantic settings with `DB_URL`
Falls back to `sqlite+aiosqlite:///./co2_calculator.db`.
