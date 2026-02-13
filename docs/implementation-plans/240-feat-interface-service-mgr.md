# Implementation Progress Report

## 📊 Summary

The audit trail infrastructure has been partially implemented with core versioning, database models, and API integration. The foundation is solid but needs external storage integration and UI exposure.

## ⚠️ Important Clarification: AUDIT vs APPLICATION Logs

| Logs Type        | Storage                    | Purpose                                         | Tools                                 |
| ---------------- | -------------------------- | ----------------------------------------------- | ------------------------------------- |
| **AUDIT** (OPDO) | `audit_documents` DB table | "Who did what when?" - Track data modifications | Internal DB + Export to ElasticSearch |
| **APPLICATION**  | Pod logs (Kubernetes)      | Debug: CPU/RAM, errors, API connectivity        | Grafana, Loki, OpenTelemetry          |

- **Travel API Logs** = APPLICATION logs (API connectivity, performance) in Kubernetes pods
- **Travel Data Imports** = AUDIT logs created when job is inserted into DB
- **User Activity** = AUDIT logs (connections, data modifications)

---

## ✅ Phase 1: What Has Been Done

### 1. **Core AUDIT Infrastructure (OPDO - DB Historical Logs)**

- ✅ Created `AuditDocument` model with versioning fields (entity_type, entity_id, version, is_current, change_type, etc.)
- ✅ Implemented `AuditChangeTypeEnum` with CREATE, READ, UPDATE, DELETE, ROLLBACK, TRANSFER
- ✅ Database migration files created for PostgreSQL/SQLite compatibility
- ✅ Hash chain integrity mechanism for tamper detection
- ✅ Tracks **what changed, when, by whom, from which IP, via which route**

### 2. **High-Performance Bulk Version Creation**

- ✅ Implemented `AuditDocumentService.bulk_create_versions()`
  - Reduces N sequential DB queries to 1 batch query
  - Single flush instead of N flushes
  - Critical for CSV import performance (1000+ entries)
- ✅ `AuditDocumentRepository.bulk_create()` for batch insertions

### 3. **Data Entry Service Versioning**

- ✅ Enhanced `DataEntryService` methods:
  - `create()` - creates version on single entry creation
  - `bulk_create()` - bulk versions with job_id context (CSV imports)
  - `bulk_delete()` - captures snapshots before deletion
  - `update()` - audit trail for modifications
  - `delete()` - records deletions
  - `get_submodule_data()` - READ audit records for OPDO compliance

### 4. **Request Context Capture**

- ✅ New `app/utils/request_context.py` - extract IP, route path, payload
- ✅ New `app/utils/audit_helpers.py` - extract user identifiers (sciper, traveler_id)
- ✅ API route handlers updated to pass request context
- ✅ Updated routes: `get_submodule`, `create`, `update`, `delete` in `carbon_report_module.py`

### 5. **User Activity Tracking (AUDIT LOGS)**

- ✅ Data Entry CREATE operations logged with user, timestamp, IP, route
- ✅ Data Entry UPDATE/DELETE operations with change snapshots
- ✅ READ operations logged (trips, member data for OPDO compliance)
- ✅ Handled IDs extracted (sciper for headcount, traveler_id for trips)
- ✅ CSV import jobs tracked (who imported, when, job_id)
- ⏳ **Authentication events** (login, logout) - NOT YET IMPLEMENTED
  - Need to add audit records for user logins to answer "qui loggé quand?"
  - Should log from auth middleware/endpoint

### 6. **Schema & DB Updates**

- ✅ Migration 1: audit_documents table creation
- ✅ Migration 2: Enum type conversion, field renaming
- ✅ UserRead schema includes provider_code
- ✅ HeadCount schemas include sciper field

---

## 🚧 Phase 2: Still Needs Implementation

### 1. **External Audit Log Storage (HIGH PRIORITY) - NOT APPLICATION LOGS**

This is for **AUDIT logs only** (who changed what in DB), NOT travel API application logs.

**EPFL Data Protection Compliance** (inside.epfl.ch/data-protection/):

- Must log all CRUD operations on **personal data** (Headcount + Travel modules with `sciper` involved)
- Must log READ operations on personal data (rule TBD: likely when `# sciper < 20`)
- **Mandatory Fields** in all audit logs:
  - `actor_id`: Identifier of person who performed processing (unique, retrievable by authorized staff)
  - `recipient_id`: Identifier of person whose data is accessed (if applicable)
  - `change_type`: Nature of processing (READ, CREATE, UPDATE, DELETE, TRANSFER)
  - `changed_at`: ISO 8601 timestamp with timezone (yyyy-mm-dd HH:MM:SS ±UTC)
- **Recommended Fields** (for compliance analysis):
  - `subject_id`: Which sciper/person's data was accessed
  - `query_summary`: Transaction/query used (e.g., "SELECT initial..." without results)
  - `source_ip`: Machine initiating processing (hostname or IP address)

- [ ] **Automatic Archival & Purge Mechanism** (Méchanisme d'archivage et purge automatique)
  - Keep audit logs in local DB for **1 year** (searchable, fast access)
  - After 1 year: automatically archive to ElasticSearch/external storage (IS-GOV)
  - **Automatic purge** from local DB after archival (no manual intervention)
  - Ensure archived logs remain immutable (write-once, read-many)
  - All EPFL compliance fields preserved during archival
  - **Scope**: Only personal data CRUD + READ operations (< 20 sciper threshold TBD)

- [ ] **Audit Log Viewing Interface** (externalized console)
  - Standalone audit log viewer (NOT embedded in app)
  - Query/filter by:
    - User (who performed action)
    - Entity type (DataEntry, User, etc.)
    - Date range (1-year local + historical from ES)
    - Action (CREATE, READ, UPDATE, DELETE, TRANSFER)
    - Subject (whose data was accessed)
  - Display: timestamp, actor, action, entity, changes, IP address
  - Read-only interface (no data modification)
  - Authorization: Service managers + admins only

### 2. **Application Observability Logs (MONITORING - SEPARATE CONCERN)**

These are **Kubernetes pod logs**, handled by DSI (not this feature):

- ⏳ Travel API connectivity logs → Loki/Grafana (NOT our responsibility)
- ⏳ CPU/RAM usage logs → OpenTelemetry
- ⏳ Error/debug logs → Pod logs
- **Note**: Travel API import **jobs** ARE tracked as audit events in audit_documents

### 3. **Authentication Audit Logging (HIGH PRIORITY) - NEW**

Add audit events for user authentication:

- [ ] **Login Events**
  - entity_type = "User"
  - entity_id = user_id
  - change_type = CREATE (new session) / TRANSFER (existing user login)
  - Track: who, when, from which IP
- [ ] **Logout Events**
  - change_type = DELETE (session ended)
- [ ] **Failed Login Attempts** (optional but recommended)
  - Track for security analysis

### 4. **Service Manager API & UI (HIGH PRIORITY)**

Query the **AUDIT logs** to answer Service Manager questions:

- [ ] **Query Endpoints**
  ```
  GET /api/v1/audit/activity
    - ?user_id=123              # Who did this user affect?
    - ?entity_type=DataEntry    # All changes to data entries
    - ?date_range=2026-01-01:2026-02-01
    - ?action=CREATE|UPDATE|DELETE|READ
    - ?entity_id=456            # History of specific entry
  ```
- [ ] **Dashboard Views**
  - "Who did what when?" timeline for selected user
  - Change history viewer (before/after diffs)
  - Bulk operation tracking (CSV imports)
  - Login/logout history
- [ ] **Export Functionality**
  - CSV export of audit logs filtered by date/user/action
  - Compliance reports
  - Evidence for investigations

### 5. **Data Retention & Compliance (MEDIUM PRIORITY) - AUDIT LOGS ONLY**

Legal requirement: Keep audit logs for 5 years minimum, with local 1-year copies.

- [ ] **1-Year Local Archive**
  - Audit logs kept in DB for quick access (1 year)
  - Indexed for fast queries
- [ ] **Long-Term External Storage**
  - After 1 year: move to ElasticSearch/cold storage
  - Keep for 5+ years per legal requirements
  - Immutable (write-once, read-many)
- [ ] **Purge Policy**
  - Automated job to archive logs older than 1 year
  - Delete from local DB after archiving
  - Ensure deleted data cannot be recovered (disk wipe/encryption)

### 6. **Travel API & Data Imports (MEDIUM PRIORITY)**

**Clarification**: Travel API connectivity logs = APPLICATION logs (pod logs), not audit logs.

- ✅ CSV import jobs ARE tracked in audit_documents (job creation event)
- ✅ Data entries created via CSV ARE tracked (entity creation events)
- ⏳ Verify travel API data imports flow through correctly
- ⏳ Test that CSV import audit trail shows correct job_id

### 7. **Testing & Validation (MEDIUM PRIORITY)**

- [ ] Unit tests:
  - `test_audit_service.py` - versioning logic, hashing
  - `test_data_entry_service_versioning.py` - integration tests
- [ ] Integration tests:
  - CSV bulk import with audit trail
  - Update/delete operations
  - Authentication logging (login/logout)
  - READ audit logging
- [ ] Performance tests:
  - Bulk 10k entry import performance
  - Query performance on audit table with 1M+ records
- [ ] Target coverage: ≥60% backend code

### 8. **Security & RBAC (MEDIUM PRIORITY)**

- [ ] Authorization checks:
  - Only service managers can view audit logs
  - Users CANNOT see other users' activity (privacy)
  - Admin has full access
- [ ] Audit log access is itself logged (create audit event when someone views logs)
- [ ] IP address validation/masking (avoid exposing internal IPs)

### 9. **Documentation (LOW PRIORITY)**

- [ ] User Guide:
  - "Activity History" section in Service Manager
  - How to find who created/modified an entry
  - Understanding the audit log timeline
- [ ] API Documentation:
  - Audit query endpoints
  - AuditChangeTypeEnum values
  - Request/response examples
- [ ] Architecture documentation:
  - "AUDIT vs APPLICATION Logs" clarification
  - Versioning system design
  - Hash chain integrity explanation
  - 1-year local + 5-year external retention model

### 10. **Operational Tasks (LOW PRIORITY)**

- [ ] Database index optimization on audit_documents
  - Index on (entity_type, entity_id, changed_at) for faster queries
  - Index on changed_by for user activity queries
- [ ] Monitoring/alerting for audit table growth
- [ ] Backup strategy for audit data (immutable copies)
- [ ] Audit log integrity verification script

---

## ❓ Open Questions for DPO/Legal Team

**Source**: EPFL Data Protection Guidelines (inside.epfl.ch/data-protection/)
**Contact**: @CDucrest-EPFL, @agletiec

1. **READ Data Logging Scope & Threshold**
   - Which READ operations must be logged to ES?
   - **Tentative Rule**: Log all READs where affected `sciper` count < 20 (to prevent data breach of "aggregated" data)
   - **Question**: Is this the correct threshold? Below what number of users does aggregated data become personally identifiable?
   - **Example**: Unit with 3 people, only 1 took a trip → logging this READ creates breach risk
   - **Need**: Exact rule from DPO on scope

2. **Headcount vs Travel Module Logging**
   - Both modules involve `sciper` (mandatory personal data subject)
   - Both require CRUD + READ audit logging
   - **Confirmed**: Both modules go to ES
   - **Need**: Confirmation on READ threshold application to both

3. **Anonymous/Aggregated Data**
   - Dashboard dashboards with aggregated stats (no individual sciper)?
   - Should these be logged? Does the < 20 rule apply?
   - **Need**: Classification of which queries are "personal data" vs "aggregated only"

4. **Data Recipient Identification**
   - When data is accessed by a report or API call, how to identify the "recipient"?
   - Is it the end-user, or the system querying on their behalf?
   - **Need**: Guidance on `recipient_id` field mapping for different query types

---

## 📋 Implementation Roadmap

### **Sprint 1 (Immediate - Week of Feb 17)**

1. ✅ Core audit infrastructure (DONE)
2. ✅ High-performance bulk versioning (DONE)
3. Write unit tests for AuditDocumentService
4. **Add authentication logging** - login/logout events (NEW)
5. Verify CSV import captures audit trail end-to-end

### **Sprint 2 (Week of Feb 24)**

1. Create audit query endpoints `/api/v1/audit/activity`
2. Implement basic Service Manager dashboard view
3. Add date-range and user filtering
4. Test authentication event logging

### **Sprint 3 (Week of Mar 3)**

1. ElasticSearch integration (requires IS-GOV access)
2. Implement 1-year archive + ES sync job
3. Create ES queries for dashboard
4. Setup purge automation (1-year trigger)

### **Sprint 4 (Week of Mar 10)**

1. 5-year retention compliance testing
2. Export functionality (CSV/JSON)
3. Archive immutability verification
4. Documentation and user guide

---

## 🎯 Success Criteria Checklist

| Criterion                          | Status         | Notes                              |
| ---------------------------------- | -------------- | ---------------------------------- |
| Activity saved in AUDIT DB         | ✅ Done        | All CRUD ops logged                |
| Authentication events logged       | ⏳ Not Started | Login/logout audit records needed  |
| Visible in Service Mgr UI          | 🚧 In Progress | API done, UI needed                |
| Query audit logs by date/user/type | ⏳ Not Started | API endpoints required             |
| Export audit log capability        | ⏳ Not Started | CSV/JSON export                    |
| User guide updated                 | ⏳ Not Started | "Activity History" section needed  |
| API docs updated                   | ⏳ Not Started | OpenAPI/Swagger                    |
| Test coverage ≥60%                 | ⏳ Not Started | Need test suite                    |
| ElasticSearch integration          | ⏳ Not Started | Awaits IS-GOV access               |
| 1-year local archive automation    | ⏳ Not Started | Cron job to move old logs          |
| 5-year retention compliance        | ⏳ Not Started | Legal requirement                  |
| Who created/modified objects       | ✅ Done        | changed_by field populated         |
| Who logged in when                 | ⏳ Not Started | Authentication audit events needed |
| Clarified AUDIT vs APP logs        | ✅ Done        | This document                      |

---

## 🔗 Next Immediate Steps

1. **Clarify scope with PM**: AUDIT logs ≠ APPLICATION logs
   - AUDIT: Who changed data in DB (our responsibility)
   - APPLICATION: Pod logs, API connectivity (DSI responsibility)

2. **Add authentication logging**
   - Implement login/logout events in audit_documents
   - Answer "qui loggé quand?" requirement

3. **Run CSV import end-to-end test**
   - Confirm audit trail works for bulk operations
   - Verify job_id tracking

4. **Define audit query API** with Service Manager team
   - What fields do they need to filter on?
   - What timeline granularity?

5. **Get ES access** from security team
   - Start planning ElasticSearch cluster use

6. **Schedule review** with code review team on audit log format/structure
   - Validate field naming conventions
   - Confirm compliance with regulations
