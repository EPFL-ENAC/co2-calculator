# Database Overview

The database layer uses PostgreSQL for persistent data storage with SQLAlchemy ORM for data access. This overview provides schema information, migration procedures, and maintenance guidelines.

For system architecture and technology decisions, see:

- [Component Breakdown](../architecture/09-component-breakdown.md) - Database layer architecture
- [Tech Stack](../architecture/08-tech-stack.md) - Why PostgreSQL
- [Data Flow](../architecture/10-data-flow.md) - Data movement patterns
- [ADR-004 Database Selection](../architecture-decision-records/004-database-selection.md) - Database decision

---

## Quick Reference

### Database Access

**Development**:

```bash
# Connect to local PostgreSQL (Docker Compose)
docker-compose exec postgres psql -U co2calculator -d co2calculator

# Or direct connection
psql postgresql://co2calculator:password@localhost:5432/co2calculator
```

**Production**: Access via Kubernetes port-forwarding or admin tools

### Common Operations

```bash
# Run migrations
cd backend
make db-migrate

# Create new migration
make db-revision message="Add user preferences"

# Rollback one migration
make db-downgrade

# View migration history
make db-history

# Database backup (production)
kubectl exec -n co2calculator postgres-0 -- pg_dump -U postgres co2calculator > backup.sql
```

---

## Database Technology

- **Engine**: PostgreSQL 15+
- **ORM**: SQLAlchemy 2.0
- **Migration Tool**: Alembic
- **Connection Pooling**: PgBouncer (production) or SQLAlchemy pooling (development)
- **Backup**: pg_dump + S3/RCP NAS storage

### Key PostgreSQL Features Used

- **JSONB**: Flexible data structures (import row validation errors)
- **ARRAY**: Multi-value columns (user roles, lab members)
- **Full-Text Search**: Search across labs and emission factors
- **Partial Indexes**: Optimize queries on filtered data
- **Foreign Key Constraints**: Enforce referential integrity
- **Check Constraints**: Enforce business rules at DB level

---

## Schema Overview

### Core Entities

```
Users
├── Laboratories (created_by)
│   ├── ImportJobs (lab_id)
│   │   └── ImportRows (import_job_id)
│   ├── Activities (lab_id)
│   └── Results (lab_id)
├── AuditLogs (user_id)
└── UserRoles (user_id)

EmissionFactors (standalone, referenced by Activities)
├── TravelFactors
├── EnergyFactors
├── PurchaseFactors
└── CustomFactors
```

### Entity Relationships

- **Users ↔ Laboratories**: One-to-Many (user creates many labs)
- **Laboratories ↔ ImportJobs**: One-to-Many (lab has many imports)
- **ImportJobs ↔ ImportRows**: One-to-Many (import has many rows)
- **Laboratories ↔ Activities**: One-to-Many (lab has many activities)
- **Activities → EmissionFactors**: Many-to-One (many activities use one factor)

### Key Tables

#### Users Table

```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sciper VARCHAR(10) UNIQUE NOT NULL,  -- EPFL unique identifier
    email VARCHAR(255) UNIQUE NOT NULL,
    display_name VARCHAR(255),
    roles TEXT[] DEFAULT ARRAY['viewer'],
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_users_sciper ON users(sciper);
CREATE INDEX idx_users_email ON users(email);
```

#### Laboratories Table

```sql
CREATE TABLE laboratories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code VARCHAR(50) UNIQUE NOT NULL,  -- Lab code (e.g., ENAC-IIE)
    name VARCHAR(255) NOT NULL,
    faculty VARCHAR(100),
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_labs_created_by ON laboratories(created_by);
CREATE INDEX idx_labs_faculty ON laboratories(faculty);
```

#### Import Jobs Table

```sql
CREATE TABLE import_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lab_id UUID REFERENCES laboratories(id) ON DELETE CASCADE,
    uploader_id UUID REFERENCES users(id),
    filename VARCHAR(255) NOT NULL,
    s3_key VARCHAR(500),  -- S3 object key
    status VARCHAR(50) DEFAULT 'pending',  -- pending, processing, completed, failed
    rows_total INTEGER DEFAULT 0,
    rows_valid INTEGER DEFAULT 0,
    rows_error INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP
);

CREATE INDEX idx_imports_lab_id ON import_jobs(lab_id);
CREATE INDEX idx_imports_status ON import_jobs(status);
CREATE INDEX idx_imports_created_at ON import_jobs(created_at DESC);
```

#### Import Rows Table

```sql
CREATE TABLE import_rows (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    import_job_id UUID REFERENCES import_jobs(id) ON DELETE CASCADE,
    row_number INTEGER NOT NULL,
    raw_data JSONB NOT NULL,  -- Original CSV row data
    validation_errors JSONB,   -- Array of validation error messages
    status VARCHAR(50) DEFAULT 'valid',  -- valid, error
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_import_rows_job ON import_rows(import_job_id);
CREATE INDEX idx_import_rows_status ON import_rows(status);
```

#### Activities Table

```sql
CREATE TABLE activities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lab_id UUID REFERENCES laboratories(id) ON DELETE CASCADE,
    import_row_id UUID REFERENCES import_rows(id),
    activity_type VARCHAR(100) NOT NULL,  -- travel, energy, purchase, service
    category VARCHAR(100),
    subcategory VARCHAR(100),
    quantity NUMERIC(15, 4) NOT NULL,
    unit VARCHAR(50) NOT NULL,
    emission_factor_id UUID REFERENCES emission_factors(id),
    co2e_kg NUMERIC(15, 4),  -- Calculated CO2 equivalent
    date DATE NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_activities_lab ON activities(lab_id);
CREATE INDEX idx_activities_type ON activities(activity_type);
CREATE INDEX idx_activities_date ON activities(date DESC);
CREATE INDEX idx_activities_factor ON activities(emission_factor_id);
```

#### Emission Factors Table

```sql
CREATE TABLE emission_factors (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code VARCHAR(100) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    category VARCHAR(100) NOT NULL,
    subcategory VARCHAR(100),
    value NUMERIC(15, 6) NOT NULL,  -- kg CO2e per unit
    unit VARCHAR(50) NOT NULL,
    source VARCHAR(255),  -- Data source (DEFRA, ADEME, custom)
    valid_from DATE,
    valid_to DATE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_factors_code ON emission_factors(code);
CREATE INDEX idx_factors_category ON emission_factors(category);
CREATE INDEX idx_factors_valid ON emission_factors(valid_from, valid_to);
```

**Full Schema**: See [`backend/app/models/`](https://github.com/EPFL-ENAC/co2-calculator/tree/main/backend/app/models) for SQLAlchemy model definitions.

---

## Migrations

### Migration Process

1. **Make schema changes** in SQLAlchemy models (`backend/app/models/*.py`)
2. **Generate migration** with Alembic auto-detection
3. **Review and customize** the generated migration script
4. **Test locally** (apply and rollback)
5. **Commit** migration script to version control
6. **Apply** to test/staging/production environments

### Creating Migrations

```bash
# Generate migration from model changes
cd backend
alembic revision --autogenerate -m "Add user preferences table"

# Review generated file: alembic/versions/XXXX_add_user_preferences_table.py

# Apply migration
alembic upgrade head

# Rollback if needed
alembic downgrade -1
```

### Migration Naming Convention

Format: `{revision}_{description}.py`

Examples:

- `001_initial_schema.py`
- `002_add_user_roles.py`
- `003_add_import_validation.py`

### Migration Best Practices

- **One purpose per migration**: Don't mix unrelated changes
- **Always test downgrade**: Ensure migrations are reversible
- **Handle data carefully**: Use separate data migrations for large datasets
- **Avoid destructive changes**: Don't drop columns with data (deprecate instead)
- **Version control**: Always commit migrations with code changes

### Data Migrations

For complex data transformations, create data-only migrations:

```python
# alembic/versions/004_migrate_old_factor_format.py
def upgrade():
    op.execute("""
        UPDATE emission_factors
        SET value = value * 1000
        WHERE unit = 'tonnes'
    """)

    op.execute("""
        UPDATE emission_factors
        SET unit = 'kg'
        WHERE unit = 'tonnes'
    """)

def downgrade():
    op.execute("""
        UPDATE emission_factors
        SET value = value / 1000
        WHERE unit = 'kg' AND value > 1000
    """)

    op.execute("""
        UPDATE emission_factors
        SET unit = 'tonnes'
        WHERE unit = 'kg' AND value < 1
    """)
```

---

## Backup & Recovery

### Backup Strategy

**Automated Backups** (Production):

- **Full backup**: Daily at 02:00 UTC
- **Incremental backup**: Every 6 hours
- **Transaction logs**: Continuous archiving
- **Retention**: 30 days on RCP NAS, 1 year archived to S3

**Manual Backups**:

```bash
# Full database backup
pg_dump -U postgres -d co2calculator -F c -f backup_$(date +%Y%m%d).dump

# Schema-only backup
pg_dump -U postgres -d co2calculator --schema-only -f schema.sql

# Data-only backup
pg_dump -U postgres -d co2calculator --data-only -f data.sql

# Specific table backup
pg_dump -U postgres -d co2calculator -t activities -F c -f activities_backup.dump
```

### Restore Procedures

```bash
# Restore full database
pg_restore -U postgres -d co2calculator -c backup.dump

# Restore specific table
pg_restore -U postgres -d co2calculator -t activities activities_backup.dump

# Restore from SQL file
psql -U postgres -d co2calculator -f backup.sql
```

### Point-in-Time Recovery (PITR)

PostgreSQL WAL archiving enables recovery to any point in time:

```bash
# Restore to specific time
recovery_target_time = '2025-11-10 14:30:00'
```

**Configuration**: See infrastructure team for PITR setup (requires WAL archiving).

---

## Performance Optimization

### Indexes

Indexes are automatically created for:

- Primary keys (`id` columns)
- Foreign keys (`*_id` columns)
- Unique constraints (`sciper`, `email`, `code`)

**Custom indexes**:

```sql
-- Speed up lab activity queries
CREATE INDEX idx_activities_lab_date ON activities(lab_id, date DESC);

-- Speed up import status filtering
CREATE INDEX idx_imports_status_created
ON import_jobs(status, created_at DESC)
WHERE status != 'completed';
```

### Query Optimization

```python
# ❌ Bad: N+1 queries
labs = session.query(Lab).all()
for lab in labs:
    print(lab.created_by.name)  # Separate query for each lab

# ✅ Good: Eager loading
labs = session.query(Lab).options(
    joinedload(Lab.created_by)
).all()
for lab in labs:
    print(lab.created_by.name)  # No additional queries
```

### Connection Pooling

**Development**: SQLAlchemy default pool (5 connections)

**Production**: PgBouncer for connection pooling

```ini
# PgBouncer configuration
[databases]
co2calculator = host=postgres port=5432 dbname=co2calculator

[pgbouncer]
pool_mode = transaction
max_client_conn = 1000
default_pool_size = 25
reserve_pool_size = 5
```

---

## Monitoring & Maintenance

### Database Monitoring

**Metrics to track**:

- Connection count (`pg_stat_activity`)
- Query performance (`pg_stat_statements`)
- Table sizes (`pg_relation_size`)
- Index usage (`pg_stat_user_indexes`)
- Bloat (dead tuples)

**Queries**:

```sql
-- Active connections
SELECT count(*) FROM pg_stat_activity WHERE state = 'active';

-- Slow queries
SELECT query, mean_exec_time
FROM pg_stat_statements
ORDER BY mean_exec_time DESC
LIMIT 10;

-- Table sizes
SELECT relname, pg_size_pretty(pg_relation_size(relid))
FROM pg_stat_user_tables
ORDER BY pg_relation_size(relid) DESC;

-- Unused indexes
SELECT schemaname, tablename, indexname
FROM pg_stat_user_indexes
WHERE idx_scan = 0
AND indexname NOT LIKE '%_pkey';
```

### Routine Maintenance

```sql
-- Vacuum and analyze (reclaim space, update statistics)
VACUUM ANALYZE;

-- Rebuild index
REINDEX INDEX idx_activities_lab_date;

-- Check for bloat
SELECT schemaname, tablename,
       pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
```

**Automated Maintenance**: PostgreSQL autovacuum handles routine maintenance automatically.

---

## Security

### Access Control

- **Application user**: Limited permissions (CRUD on application tables)
- **Admin user**: Full database access (for migrations, backups)
- **Read-only user**: SELECT only (for reporting, analytics)

```sql
-- Create application user
CREATE USER co2calculator_app WITH PASSWORD 'strong_password';
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO co2calculator_app;

-- Create read-only user
CREATE USER co2calculator_readonly WITH PASSWORD 'readonly_password';
GRANT SELECT ON ALL TABLES IN SCHEMA public TO co2calculator_readonly;
```

### Data Encryption

- **At rest**: PostgreSQL supports transparent data encryption (TDE)
- **In transit**: SSL/TLS connections required in production
- **Connection string**: `postgresql://user:pass@host:5432/db?sslmode=require`

### Sensitive Data

- **Passwords**: Never stored in database (authentication via OIDC)
- **PII**: User email and SCIPER (encrypted backups)
- **Audit logs**: Track data access and modifications

---

## Troubleshooting

### Connection Issues

```bash
# Check PostgreSQL is running
docker-compose ps postgres

# Check connection from backend
psql $DATABASE_URL -c "SELECT 1;"

# View connection errors in logs
docker-compose logs postgres | grep ERROR
```

### Migration Issues

```bash
# Check current migration version
alembic current

# View migration history
alembic history

# Force set version (if out of sync)
alembic stamp head

# Rollback problematic migration
alembic downgrade -1
```

### Performance Issues

```bash
# Check for blocking queries
SELECT pid, query, state
FROM pg_stat_activity
WHERE wait_event_type = 'Lock';

# Kill blocking query (if needed)
SELECT pg_terminate_backend(pid);

# Check table bloat
VACUUM VERBOSE ANALYZE activities;
```

---

## Additional Resources

### Architecture Documentation

- [System Overview](../architecture/02-system-overview.md) - Database in system context
- [Data Flow](../architecture/10-data-flow.md) - How data moves through the system
- [Component Breakdown](../architecture/09-component-breakdown.md#database-layer) - Database architecture

### PostgreSQL Documentation

- [PostgreSQL Official Docs](https://www.postgresql.org/docs/)
- [SQLAlchemy ORM](https://docs.sqlalchemy.org/en/20/)
- [Alembic Migrations](https://alembic.sqlalchemy.org/)

---

**Last Updated**: November 11, 2025  
**Readable in**: ~8 minutes
