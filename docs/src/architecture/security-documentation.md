# Security Documentation Index

Maps the ten documents ENAC-IT requires for this service to where each
one actually lives. Most were already written as ordinary engineering
docs; this page is what makes them findable as a set. Start here when
answering a security questionnaire or an audit.

**Reading time**: ~4 minutes

## The ten required documents

| #   | Required document          | Where it lives                                                                                                                                                                                                                                                                                               | State       |
| --- | -------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ----------- |
| 1   | Encryption keys management | [Encryption and Key Management](encryption.md)                                                                                                                                                                                                                                                               | ✅ Complete |
| 2   | Operating procedures       | [Release runbook](release-runbook.md), [Infra overview](../infra/01-overview.md)                                                                                                                                                                                                                             | ✅ Complete |
| 3   | Change management          | [Guardrails § Workflow](../contributing/guardrails.md), [Release management](release-management.md), [Workflow guide](workflow-guide.md)                                                                                                                                                                     | ✅ Complete |
| 4   | Malicious code detection   | [ADR-014 §1, §2, §6](../architecture-decision-records/014-security-checklist.md) — Dependabot, CodeQL, secret scanning, Trivy                                                                                                                                                                                | ✅ Complete |
| 5   | Vulnerability monitoring   | [ADR-014 §1, §2](../architecture-decision-records/014-security-checklist.md), [CI/CD workflows](cicd-workflows.md)                                                                                                                                                                                           | ✅ Complete |
| 6   | Third-party list           | [Third parties](#third-parties) below; dependency-level detail in the repository's GitHub dependency graph                                                                                                                                                                                                   | ✅ Complete |
| 7   | Incident response          | [Incident Response](incident-response.md) — severity tiers, communication timeframes, confidentiality, and the personal-data notification; responder roster in the [Disaster Recovery Plan](https://github.com/EPFL-ENAC/openshift-app-config/blob/main/epfl/co2-calculator/DRP.md) (private ops repository) | ✅ Complete |
| 8   | Business continuity plan   | [Disaster Recovery Plan](https://github.com/EPFL-ENAC/openshift-app-config/blob/main/epfl/co2-calculator/DRP.md) (private ops repository) — recovery team, namespace and bucket re-provisioning, secret recovery, GitOps and ArgoCD restore, database restore, manual build path, monitoring recovery        | ✅ Complete |
| 9   | Maintenance and restore    | [Release runbook](release-runbook.md), [Disaster Recovery Plan](https://github.com/EPFL-ENAC/openshift-app-config/blob/main/epfl/co2-calculator/DRP.md) (private ops repository), backup section of [Infra overview](../infra/01-overview.md), [Recovery objectives](#recovery-objectives)                   | ✅ Complete |
| 10  | Compliance procedures      | [EPFL compliance mapping](epfl-compliance-mapping.md), [EPFL constraints](epfl-constraint.md)                                                                                                                                                                                                                | ✅ Complete |

## What is still open

- **Recovery timeframes (9)** — best effort, documented under
  [Recovery objectives](#recovery-objectives). Detection is measured
  and fast; database restore depends on EPFL DSI, who have not
  published a DBaaS RPO or RTO, and deleted objects are not
  recoverable at all. Both are decisions to take, not code to write.

Neither gap is closed by a code change. Track them as issues rather
than leaving them implied by an unticked box.

## Recovery objectives

**Best effort. No contractual SLA, RPO or RTO is agreed** — stating
that plainly is more useful than leaving question marks in the DRP.
What _is_ measured:

| Stage                | Actual capability                                                                                                                                                                                |
| -------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Detection            | 1–10 minutes. `PodOOMKilled` fires at 1 min; `PodNotReady`, `PVCAlmostFull` and `ImagePullBackOff` at 5 min; `BackendMetricsAbsent`, the total-outage detector, at 10 min                        |
| Application symptoms | 5 minutes — latency P50/P95/P99 and error-rate alerts; upload and job SLO breaches at 15 min                                                                                                     |
| Notification         | ~30 s after an alert fires, by email to the sysadmin group; re-sent every 4 h until resolved, and again on recovery                                                                              |
| External check       | Icinga probes HTTPS, certificate validity and the database from outside the cluster                                                                                                              |
| Restore, application | Minutes — ArgoCD auto-sync and self-heal reconcile a bad deploy; revert the GitOps commit and it rolls back                                                                                      |
| Restore, database    | **Not under our control** — requested from EPFL DSI by ticket; DSI has not published DBaaS RPO or RTO                                                                                            |
| Restore, files       | **Not possible, by decision** — buckets have versioning disabled. Object storage stages ingestion files; the durable record is in PostgreSQL, and a lost CSV is re-uploaded rather than restored |

Detection and application recovery are ours and are fast. Database
recovery depends on EPFL DSI, who publish no DBaaS RPO or RTO — that is
the one remaining unknown, and it is a conversation, not a code change.

Object storage is deliberately not versioned. It holds ingestion files
in transit (`tmp/`, `processing/`, `processed/`); the emission data they
produce lives in PostgreSQL and is backed up there. Paying for version
history on a staging area would protect a copy, not the record.

Alert rules and routing live in the private ops repository under
`overlays/<env>/monitoring/`.

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
