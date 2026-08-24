# Security Documentation Index

Maps the ten documents ENAC-IT requires for this service to where each
one actually lives. Most were already written as ordinary engineering
docs; this page is what makes them findable as a set. Start here when
answering a security questionnaire or an audit.

**Reading time**: ~4 minutes

## The ten required documents

| #   | Required document          | Where it lives                                                                                                                                                             | State       |
| --- | -------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------- |
| 1   | Encryption keys management | [Encryption and Key Management](encryption.md)                                                                                                                             | ✅ Complete |
| 2   | Operating procedures       | [Release runbook](release-runbook.md), [Infra overview](../infra/01-overview.md)                                                                                           | ✅ Complete |
| 3   | Change management          | [Guardrails § Workflow](../contributing/guardrails.md), [Release management](release-management.md), [Workflow guide](workflow-guide.md)                                   | ✅ Complete |
| 4   | Malicious code detection   | [ADR-014 §1, §2, §6](../architecture-decision-records/014-security-checklist.md) — Dependabot, CodeQL, secret scanning, Trivy                                              | ✅ Complete |
| 5   | Vulnerability monitoring   | [ADR-014 §1, §2](../architecture-decision-records/014-security-checklist.md), [CI/CD workflows](cicd-workflows.md)                                                         | ✅ Complete |
| 6   | Third-party list           | [Third parties](#third-parties) below; dependency-level detail in the repository's GitHub dependency graph                                                                 | ✅ Complete |
| 7   | Incident response          | 5-step procedure in the private security repository; [SLO and alerting](../infra/03-observability-slo.md); [worked example](../infra/02-postmortem-oauth-http-redirect.md) | ⚠️ Partial  |
| 8   | Business continuity plan   | —                                                                                                                                                                          | ❌ Missing  |
| 9   | Maintenance and restore    | [Release runbook](release-runbook.md), backup section of [Infra overview](../infra/01-overview.md)                                                                         | ✅ Complete |
| 10  | Compliance procedures      | [EPFL compliance mapping](epfl-compliance-mapping.md), [EPFL constraints](epfl-constraint.md)                                                                              | ✅ Complete |

## What is still open

- **Incident response (7)** — a procedure exists, but the requirement
  asks for two things it does not state: **how fast** an incident is
  communicated, and the **confidentiality level** of that
  communication. Both are policy decisions, not engineering ones.
- **Business continuity (8)** — not written.

Neither gap is closed by a code change. Track them as issues rather
than leaving them implied by an unticked box.

## Third parties

Services this deployment depends on:

| Service                | Role                                            |
| ---------------------- | ----------------------------------------------- |
| Microsoft Entra ID     | Authentication and authorization (OIDC)         |
| EPFL DSI PostgreSQL    | Application database                            |
| EPFL S3                | Object storage for uploads and ingestion files  |
| ENAC-IT Infisical      | Secret and encryption-key vault                 |
| EPFL Tableau           | Source of travel and headcount data             |
| European Central Bank  | Exchange-rate reference data                    |
| GitHub                 | Source hosting, CI/CD, image registry, scanning |
| OpenShift / Kubernetes | Runtime platform                                |

Library and package dependencies are not listed here — they change too
often for a hand-maintained list to stay honest. The GitHub dependency
graph is the source of truth, and Dependabot watches it.

## Ownership and review cadence

| Document                      | Owner           | Reviewed                    |
| ----------------------------- | --------------- | --------------------------- |
| This index                    | Lead developer  | Annually, and on any change |
| Encryption and key management | Lead developer  | On any encryption change    |
| Operating and restore docs    | Lead developer  | Before each major release   |
| Third-party list              | Project manager | Quarterly                   |
| Incident response, BCP        | Project manager | Annually                    |

A document that changes without this index changing is the failure mode
this page exists to prevent — update both in the same PR.
