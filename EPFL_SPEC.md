Here’s an **RFC-style equivalent** of the *EPFL IT Standards – CalculateurCO2@EPFL (Annexe 8)* document — condensed for clarity and readability, while preserving all core requirements.

---

# RFC: EPFL IT Requirements Specification

**Author:** F. Pitteloud
**Version:** 1.0
**Date:** 05.02.2025

---

## 1. Purpose

This RFC defines the mandatory and recommended IT requirements for any new technical solution acquired or deployed at EPFL. Compliance ensures interoperability, maintainability, and alignment with EPFL infrastructure standards.

---

## 2. Authentication & Authorization (SVC0018)

| Priority | Requirement                                                                        |
| -------- | ---------------------------------------------------------------------------------- |
| P0       | MUST support strong authentication mechanisms.                                     |
| P0       | MUST support **OpenID Connect (OIDC)**.                                            |
| P0       | MUST support **OAuth 2.0+**.                                                       |
| P1       | SHOULD support **SAML 2.0+**.                                                      |
| P2       | MAY support **SCIM** for identity provisioning.                                    |
| Note     | **LDAPS** is deprecated — does not meet EPFL’s strong authentication requirements. |

---

## 3. Infrastructure as Code (IaC) /!\

| Priority | Requirement                                                        |
| -------- | ------------------------------------------------------------------ |
| P2       | MAY support **Ansible** or **Puppet**.                             |
| P1       | SHOULD support **Ansible**.                                        |
| P1       | SHOULD support **Puppet**.                                         |
| Note     | IaC support is desired for automated deployment and orchestration. |

---

## 4. Virtualization (Hypervisors) /!\

| Priority | Requirement                                        |
| -------- | -------------------------------------------------- |
| P0       | MUST support hypervisor upgrades.                  |
| P0       | MUST support **VMware** (including HA mechanisms). |

---

## 5. Containers

| Priority | Requirement                                  |
| -------- | -------------------------------------------- |
| P0       | MUST support OS patching and upgrades.       |
| P0       | MUST use **OCI-compliant** container images. |
| P1       | SHOULD support **Docker** if OCI-compliant.  |

---

## 6. Server Operating Systems (SVC1168; SVC1215) /!\ NO!?

| Priority | Requirement                                        |
| -------- | -------------------------------------------------- |
| P0       | MUST support OS patching and upgrades.             |
| P0       | MUST support **Windows Server**.                   |
| P0       | MUST support **Red Hat Enterprise Linux**.         |
| P0       | MUST support **SUSE Enterprise Linux** (SAP-only). |

---

## 7. Client Operating Systems /!\

| Priority | Requirement                             |
| -------- | --------------------------------------- |
| P0       | MUST support OS patching and upgrades.  |
| P0       | MUST support **Windows** and **macOS**. |
| P2       | MAY support **Linux**.                  |

---

## 8. Databases (SVC0020; SVC0021) /!\

| Priority | Requirement                  |
| -------- | ---------------------------- |
| P0       | MUST support **SQL Server**. |
| P0       | MUST support **MariaDB**.    |

---

## 9. Antivirus (SVC0062) /!\

| Priority | Requirement                                             |
| -------- | ------------------------------------------------------- |
| P0       | MUST comply with EPFL antivirus standards and policies. |
| Note     | Exceptions must be approved by **IT Security**.         |

---

## 10. Backup (SVC0003) /!\

| Priority | Requirement                                       |
| -------- | ------------------------------------------------- |
| P0       | MUST support EPFL’s backup solution and strategy. |
| Note     | Exceptions must be approved by **IT Security**.   |

---

## 11. Log Management /!\

| Priority | Requirement                                              |
| -------- | -------------------------------------------------------- |
| P0       | MUST provide logs compatible with **EPFL SIEM Service**. |
| Note     | Exceptions require **IT Security** approval.             |

---

## 12. Monitoring (SVC0345) /!\

| Priority | Requirement                                             |
| -------- | ------------------------------------------------------- |
| P0       | MUST support monitoring by **EPFL End-to-End Service**. |
| Note     | Exceptions require **IT Service Manager** approval.     |

---

### Priority Legend

* **P0 – Must:** Mandatory requirement
* **P1 – Acceptable:** Strongly recommended
* **P2 – Nice:** Optional

---

Would you like me to format it into an actual **RFC-formatted Markdown or PDF** (with numbered sections, abstract, and consistent headings like *RFC 2119 style keywords*)? That would make it suitable for internal documentation or Git repository inclusion.
