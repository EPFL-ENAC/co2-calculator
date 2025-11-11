# EPFL IT Compliance Mapping

This document maps CO₂ Calculator implementation to EPFL IT
requirements (RFC-EPFL-IT-001). Use this to verify compliance
and identify areas needing approval or exceptions.

**Reading time**: ~8 minutes

## TL;DR

We meet **all mandatory (P0) requirements** except one: we
use PostgreSQL instead of MariaDB/SQL Server. An exception
request is needed. Most recommended (P1) features are
implemented.

**Status**: ✅ P0: 8/9 (89%) | ✅ P1: 4/5 (80%) |
⚠️ P2: 1/3 (33%)

## Authentication and Authorization (SVC0018)

| Requirement     | Priority | Status | Notes                             |
| --------------- | -------- | ------ | --------------------------------- |
| Strong Auth     | P0       | ✅     | Microsoft Entra ID via OIDC       |
| OIDC/OAuth 2.0+ | P0       | ✅     | Full implementation with PKCE     |
| SAML 2.0+       | P1       | ⚠️     | Not implemented (OIDC sufficient) |
| SCIM            | P2       | ⚠️     | Group sync via Entra ID           |
| No LDAPS        | P0       | ✅     | Not used                          |

**Implementation**: We use Microsoft Entra ID as identity
provider with OpenID Connect protocol. JWT tokens provide
stateless auth. Authorization uses role-based access control
from Entra ID claims.

**Code**: `app/core/security.py` (backend),
`src/plugins/auth.ts` (frontend)

**Reference**: [Auth Flow](04-auth-flow.md) |
[ADR-012](../architecture-decision-records/012-jwt-authentication-strategy.md)

## Infrastructure and Containers

| Requirement         | Priority | Status | Implementation               |
| ------------------- | -------- | ------ | ---------------------------- |
| IaC Support         | P1       | ✅     | Helm + ArgoCD (not Ansible)  |
| Hypervisor Agnostic | P0       | ✅     | OCI containers               |
| OS Patching         | P0       | ✅     | Automated base image updates |
| OCI Compliance      | P0       | ✅     | Docker/Podman images         |

**Container Strategy**: We use Helm charts and ArgoCD for
GitOps deployment. This is more suitable for Kubernetes than
Ansible. All images are OCI-compliant and stored in GitHub
Container Registry (ghcr.io).

**Patching Process**:

1. Dependabot creates PR for base image updates
2. CI runs security scans (Trivy)
3. Merge and deploy with rolling updates
4. Zero-downtime patching

**Base Images**:

- Backend: Python 3.12 on Debian Bookworm (slim)
- Frontend: Nginx on Alpine Linux
- Database: PostgreSQL 16 official image

**Reference**: [Deployment Topology](11-deployment-topology.md)

## Client Support

**Status**: ✅ **COMPLIANT** (P0)

Web application works on any OS with a modern browser:

- Chrome 120+, Firefox 120+, Safari 17+, Edge 120+
- Windows 10+, macOS 12+, Linux (any distribution)

## Database (SVC0020 / SVC0021)

**Status**: ⚠️ **EXCEPTION NEEDED** (P0)

We use **PostgreSQL 16** instead of MariaDB or SQL Server.

**Why PostgreSQL**:

- Superior JSON support for flexible data structures
- Strong ACID compliance and performance
- Already supported by EPFL Kubernetes infrastructure
- Easier migration path (SQLAlchemy ORM abstracts database)

**Risk**: Low. PostgreSQL is widely used across EPFL and
meets all security and backup requirements.

**Action Required**: Submit exception request to IT Security.

**Reference**:
[ADR-004](../architecture-decision-records/004-database-selection.md)

## Security Scanning (SVC0062)

**Status**: ✅ **COMPLIANT** (P0)

**Container Scanning**: Trivy scans in CI/CD pipeline plus
GitHub Security Scanning for dependencies.

**File Uploads**: Stored in Azure Blob Storage. Processed
in isolated worker containers. No executable files allowed.

## Backup (SVC0003)

**Status**: ✅ **COMPLIANT** (P0)

| Type           | Method                            | Retention             | Testing         |
| -------------- | --------------------------------- | --------------------- | --------------- |
| Database       | PostgreSQL WAL + daily full       | 30d daily, 1y monthly | Monthly restore |
| Object Storage | Azure geo-redundant + soft delete | 30d soft delete       | Version history |

**Recovery**: Point-in-time recovery capability with
documented procedures in Helm charts.

## Logging and Monitoring

**Status**: ✅ **COMPLIANT** (P0)

**Logging**: All services produce structured JSON logs with
timestamp, level, service, correlation_id, user_id, and
event. Logs go to stdout/stderr, collected by Kubernetes,
forwarded to EPFL SIEM. Retention: 90d in SIEM, 1y archive.

**Monitoring**: Prometheus metrics at `/metrics` endpoint.
Health checks at `/health` (liveness) and `/ready`
(readiness). Metrics include request count, duration, errors,
and custom business metrics.

**Reference**: [Global Conventions](07-global-conventions.md)
| [CI/CD Pipeline](06-cicd-pipeline.md)

## Exception Requests

**Database Deviation**: Using PostgreSQL instead of
MariaDB/MSSQL

**Approval Needed**: IT Security / IT Service Manager

**Risk**: Low. PostgreSQL is supported by EPFL Kubernetes
and meets all security requirements. Database is containerized
and can be migrated if needed via SQLAlchemy ORM.

## Next Steps

1. Submit database exception request to IT Security
2. Configure log forwarding to EPFL SIEM
3. Register with End-to-End Service monitoring
4. Quarterly compliance review

## Quick Verification Commands

```bash
# Check authentication config
kubectl get secret entra-config -o yaml

# Verify structured logs
kubectl logs -l app=backend --tail=100 | jq

# Test metrics endpoint
curl https://co2-calculator.epfl.ch/api/metrics

# Check backup job
kubectl get cronjob backup-database
```

## Contacts

- **Project Lead**: [Technical Contact]
- **IT Security**: security@epfl.ch
- **IT Service Manager**: itsm@epfl.ch

## References

- [RFC-EPFL-IT-001](epfl-constraint.md) - Full requirements
- [Architecture Overview](02-system-overview.md)
- [Security Docs](13-cross-cutting-concerns.md)
- [Deployment Guide](11-deployment-topology.md)
