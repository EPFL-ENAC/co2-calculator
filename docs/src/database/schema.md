# Database Schema

This document describes the database schema, including tables, relationships, and design principles.

## Schema Design Principles

TODO: Document schema design guidelines

### Normalization

- Normalization levels
- Denormalization strategies
- Performance considerations
- Data integrity rules

### Naming Conventions

- Table naming standards
- Column naming standards
- Constraint naming
- Index naming

### Data Types

- Primary key strategies
- String length considerations
- Numeric precision and scale
- Date and time handling
- JSON storage patterns

## Entity Relationship Diagram

TODO: Insert ERD diagram

### Core Entities

- Users
- Laboratories
- Import Jobs
- Import Rows
- Emission Factors
- Activities
- Audit Logs

### Relationships

- One-to-many relationships
- Many-to-many relationships
- Self-referencing relationships
- Weak entities

## Table Definitions

TODO: Document detailed table structures

### Users Table

- id (Primary Key)
- sciper (Unique)
- email
- display_name
- created_at

### Laboratories Table

- id (Primary Key)
- code (Unique)
- name
- faculty
- created_at

### Import Jobs Table

- id (Primary Key)
- lab_id (Foreign Key)
- uploader_id (Foreign Key)
- filename
- s3_key
- status
- rows_count
- error_count
- created_at
- processed_at

### Import Rows Table

- id (Primary Key)
- import_job_id (Foreign Key)
- row_number
- raw_data (JSONB)
- validated
- errors (JSONB)

### Emission Factors Table

- id (Primary Key)
- source
- category
- key
- factor
- unit
- meta (JSONB)
- valid_from
- valid_to

### Activities Table

- id (Primary Key)
- lab_id (Foreign Key)
- type
- payload (JSONB)
- emissions_kg
- created_at

### Audit Logs Table

- id (Primary Key)
- actor_id (Foreign Key)
- action
- target_type
- target_id
- details (JSONB)
- created_at

## Indexing Strategy

TODO: Document indexing approaches

### Primary Indexes

- Primary key indexes
- Unique constraint indexes
- Foreign key indexes

### Performance Indexes

- Frequently queried columns
- Composite indexes
- Partial indexes
- Expression indexes

### Specialized Indexes

- Full-text search indexes
- JSONB path indexes
- Geospatial indexes (if applicable)
- Time-series indexes

## Constraints and Validation

TODO: Document data integrity rules

### Database Constraints

- Primary key constraints
- Foreign key constraints
- Unique constraints
- Check constraints
- Not-null constraints

### Application-Level Validation

- Business rule enforcement
- Cross-field validation
- Data format validation
- Referential integrity

For migration procedures, see [Migrations](./migrations.md).
