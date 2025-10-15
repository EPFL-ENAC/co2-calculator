# RFC-EPFL-IT-001: IT Requirements Specification

**Author:** F. Pitteloud  
**Version:** 1.0  
**Date:** 05.02.2025

---

## 1. Scope

This RFC defines the mandatory (**P0**), recommended (**P1**), and optional (**P2**) technical requirements for any IT solution deployed or acquired by EPFL.  
Compliance ensures interoperability, maintainability, and alignment with EPFL infrastructure standards.

---

## 2. Authentication and Authorization (SVC0018)

2.1 Solutions **MUST** support strong authentication mechanisms.  
2.2 Solutions **MUST** support **OpenID Connect (OIDC)** and **OAuth 2.0+**.  
2.3 Solutions **SHOULD** support **SAML 2.0+**.  
2.4 Solutions **MAY** support **SCIM** for identity provisioning.  
2.5 **LDAPS** is **PROHIBITED** (does not meet EPFL strong auth requirements).

---

## 3. Infrastructure as Code (IaC)

3.1 Solutions **SHOULD** support **Ansible** or **Puppet** for deployment and orchestration.  
3.2 IaC integration **MAY** be used to automate configuration management.

---

## 4. Virtualization / Hypervisors

4.1 Solutions **MUST** support hypervisor upgrades.  
4.2 Solutions **MUST** support **VMware**, including high-availability mechanisms.

---

## 5. Containers

5.1 Containerized solutions **MUST** support OS patching and upgrades.  
5.2 Container images **MUST** be **OCI-compliant**.  
5.3 **Docker** images **SHOULD** be used only if OCI-compliant.

---

## 6. Server Operating Systems (SVC1168 / SVC1215)

6.1 Solutions **MUST** support OS patching and upgrade cycles.  
6.2 Supported server OS:

- **Windows Server**
- **Red Hat Enterprise Linux**
- **SUSE Enterprise Linux** (SAP-only)

---

## 7. Client Operating Systems

7.1 Solutions **MUST** support OS patching and upgrade cycles.  
7.2 Supported client OS:

- **Windows**
- **macOS**
- **Linux** (_optional_)

---

## 8. Databases (SVC0020 / SVC0021)

8.1 Supported databases:

- **SQL Server** (**MUST**)
- **MariaDB** (**MUST**)

---

## 9. Antivirus (SVC0062)

9.1 Solutions **MUST** comply with EPFL antivirus standards and policies.  
9.2 Any deviation **MUST** be approved by **IT Security**.

---

## 10. Backup (SVC0003)

10.1 Solutions **MUST** support EPFL’s official backup solution and strategy.  
10.2 Any exception **MUST** be validated by **IT Security**.

---

## 11. Log Management

11.1 Solutions **MUST** provide logs compatible with the **EPFL SIEM** service.  
11.2 Exceptions **MUST** be approved by **IT Security**.

---

## 12. Monitoring (SVC0345)

12.1 Solutions **MUST** be monitorable by **EPFL End-to-End Service**.  
12.2 Exceptions **MUST** be validated by the **IT Service Manager**.

---

## 13. Priority Levels

| Code | Level      | Meaning                              |
| ---- | ---------- | ------------------------------------ |
| P0   | **MUST**   | Mandatory requirement                |
| P1   | **SHOULD** | Recommended / acceptable alternative |
| P2   | **MAY**    | Optional / nice-to-have              |

---

_End of RFC-EPFL-IT-001_
