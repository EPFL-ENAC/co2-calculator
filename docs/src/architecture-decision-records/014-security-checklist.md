# ADR-014: Security Checklist

**Status**: Accepted  
**Date**: 2026-02-16<br/>
**Deciders**: Development Team

---

## 1. Dependency and Library Management

### Mitigation Measures

- Ensure automated dependency monitoring with **GitHub Dependabot**.
- Configure `dependabot.yml` to:
  - Scan all ecosystems used by the project (`npm`, `pip`, and optionally `github-actions`).
  - Automatically create pull requests for dependency updates, including GitHub Actions versions.
- Dependabot PRs must be reviewed and merged promptly, particularly those flagged with security risk.

### Actions

#### Development Phase

- [x] Add or update `.github/dependabot.yml` with appropriate ecosystems and update schedule (e.g., `weekly`). — [`.github/dependabot.yml`](https://github.com/EPFL-ENAC/co2-calculator/blob/dev/.github/dependabot.yml)
- [x] Configure Dependabot settings in repository. — repository Security settings — Dependabot alerts and security updates enabled
- [x] Assign a maintainer to be responsible for managing dependabot alerts and PRs. — [`.github/CODEOWNERS`](https://github.com/EPFL-ENAC/co2-calculator/blob/dev/.github/CODEOWNERS)

#### Exploitation Phase

- [ ] Review and merge Dependabot PRs promptly.
- [ ] Monitor and triage security alerts.
- [ ] Update dependencies when vulnerabilities are reported.

### Responsibility

- **Development Phase:** lead dev
- **Exploitation Phase:** code reviewer

### Frequency

- **Development Phase:** One-time setup
- **Exploitation Phase:**
  - Dependabot PR review: within 48 hours of creation
  - Security alert triage: within 24 hours
  - Critical vulnerability updates: within 24 hours
  - High vulnerability updates: within 1 week

### Validation

- Check repository settings to ensure Dependabot alerts are enabled.
- Confirm that Dependabot PRs appear regularly.
- Verify CI successfully runs and passes on Dependabot PRs.
- Periodically inspect the dependency graph for unresolved alerts.

### Failure Handling

- If a high/critical vulnerability is reported:
  - Mark the corresponding PR as high priority.
  - If an update cannot be merged, document the risk in an issue.
- If Dependabot is inactive or misconfigured:
  - Re-enable and correct configuration immediately.

---

## 2. Automated Security Scanning in CI/CD

### Mitigation Measures

- Integrate security scanning into GitHub Actions workflows.
- Security scans should run on:
  - Every pull request
  - Every push/merge to `main`, `dev`, or other protected branches
  - Scheduled periodic runs (e.g., nightly)

### Tools to Enable

- **CodeQL Static Analysis** via GitHub’s `codeql-action` for code scanning.
- GitHub **Secret scanning** (enabled by default for public repos).
- Optionally SonarCloud or other SAST tools for additional coverage.

### Actions

#### Development Phase

- [x] Add a `codeql-analysis.yml` workflow under `.github/workflows`. — [`security.yml`](https://github.com/EPFL-ENAC/co2-calculator/blob/dev/.github/workflows/security.yml)
- [x] Configure security scanning tools and integration. — [`security.yml`](https://github.com/EPFL-ENAC/co2-calculator/blob/dev/.github/workflows/security.yml)
- [x] Set up scheduled periodic scans. — [`security.yml`](https://github.com/EPFL-ENAC/co2-calculator/blob/dev/.github/workflows/security.yml) weekly, [`image-vulnerability-scan.yml`](https://github.com/EPFL-ENAC/co2-calculator/blob/dev/.github/workflows/image-vulnerability-scan.yml) weekly
- [x] Ensure secret scanning is enabled in the repository's Security tab. — repository Security settings — secret scanning and push protection both enabled

#### Exploitation Phase

- [ ] Monitor security scan results on each PR and merge.
- [ ] Review and triage security findings.
- [ ] Fix detected vulnerabilities or document false positives.

### Responsibility

- **Development Phase:** lead dev
- **Exploitation Phase:** code reviewer

### Frequency

- **Development Phase:** One-time setup
- **Exploitation Phase:**
  - Security scan review: on every PR (before approval)
  - Scheduled scans: weekly (every Monday)
  - Vulnerability triage: within 24 hours of detection
  - Critical findings: fix before merge (blocking)
  - High findings: fix within 1 week

### Validation

- Review CI logs to confirm CodeQL runs and reports results.
- Confirm that failing findings block PR merges when configured.
- Periodically simulate a failure (e.g., introduce a detectable issue) to confirm enforcement.

### Failure Handling

- A workflow failure due to a detected issue:
  - Must be fixed before merge.
  - If false positive, document justification and escalate to the team.

---

## 3. Secure Coding and Code Review Practices

### Mitigation Measures

- Require **code reviews** for all merge requests into protected branches.
- Enforce GitHub **branch protection rules**:
  - Require status checks to pass (including security scans)
  - Require at least one approved review
- Emphasize review focus on authentication, authorization, and data validation logic.

### Actions

#### Development Phase

- [ ] Enable branch protection in repo settings:
  - [x] Require pull request reviews — `dev` and `release-line` rulesets, 1 approval
  - [ ] Require passing status checks before merge
- [x] Add security guidance to the pull request template. — [`PULL_REQUEST_TEMPLATE.md`](https://github.com/EPFL-ENAC/co2-calculator/blob/dev/.github/PULL_REQUEST_TEMPLATE.md)
- [x] Define code review guidelines with security focus. — [Code standards § Security](../architecture/code-standards.md), [Guardrails](../contributing/guardrails.md)

#### Exploitation Phase

- [ ] Perform code reviews on all pull requests.
- [ ] Verify security checks pass before approving merges.
- [ ] Ensure branch protection rules remain enforced.

### Responsibility

- **Development Phase:** project manager
- **Exploitation Phase:** code reviewer

### Frequency

- **Development Phase:** One-time setup
- **Exploitation Phase:**
  - Code review: on every PR (mandatory before merge)
  - Branch protection audit: monthly
  - PR template review: quarterly

### Validation

- Periodically verify that:
  - Branch protection rules remain enabled
  - Merges occur only after CI and reviews pass

### Failure Handling

- If merging bypasses security checks:
  - Flag immediately
  - Restore branch protection rules
  - Audit recent merges for potential issues

---

## 4. Authentication Integration Hardening

### Mitigation Measures

- Centralize authentication logic and do not trust frontend-provided identity or role information.
- Explicitly validate authentication claims from the university identity provider.
- Document authentication assumptions in code and documentation.
- Implement unit and integration tests targeting authentication, authorization, and error cases.

### Actions

#### Development Phase

- [x] Design and implement centralized authentication logic. — [`app/core/security.py`](https://github.com/EPFL-ENAC/co2-calculator/blob/dev/backend/app/core/security.py) — `is_permitted`, `check_permission`, `require_permission`
- [x] Add tests for:
  - [x] Missing or invalid authentication tokens — [`test_auth_security.py`](https://github.com/EPFL-ENAC/co2-calculator/blob/dev/backend/tests/integration/v1/test_auth_security.py) — `test_jwt_alg_none_rejected`, `test_jwt_tampered_signature_rejected`, `test_jwt_expired_rejected`
  - [x] Incorrect role/claim combinations — [`test_auth_security.py`](https://github.com/EPFL-ENAC/co2-calculator/blob/dev/backend/tests/integration/v1/test_auth_security.py) — `test_jwt_with_swapped_institutional_id_rejected`, `test_me_rejects_unknown_provider_int`
  - [x] Unauthorized access attempts — [`test_permission_scope_e2e.py`](https://github.com/EPFL-ENAC/co2-calculator/blob/dev/backend/tests/integration/v1/test_permission_scope_e2e.py), [`test_security_gates.py`](https://github.com/EPFL-ENAC/co2-calculator/blob/dev/backend/tests/unit/core/test_security_gates.py) — `test_principal_on_other_unit_denied`, `test_no_roles_denied`, `test_check_permission_raises_403_when_denied`
- [x] Document authentication assumptions and architecture. — [Auth flow § Trust boundaries](../architecture/04-auth-flow.md)

#### Exploitation Phase

- [ ] Review authentication logic during code reviews.
- [ ] Maintain and update authentication tests.
- [ ] Monitor and address authentication-related issues.

### Responsibility

- **Development Phase:** lead dev
- **Exploitation Phase:** code reviewer

### Frequency

- **Development Phase:** One-time implementation
- **Exploitation Phase:**
  - Code review for auth changes: on every auth-related PR
  - Test maintenance: on every auth change
  - Auth logic audit: quarterly
  - Test coverage verification: before each release

### Validation

- Reviews that validate test coverage for authentication logic.
- Automated tests must cover key failure cases.

### Failure Handling

- If authentication or authorization failures are discovered:
  - Treat as high priority.
  - Fix immediately with regression tests.

---

## 5. Periodic Manual Security Review

### Mitigation Measures

- Schedule periodic manual reviews focusing on:
  - Authorization logic
  - Newly added endpoints
  - Business logic changes
  - Authentication integration assumptions

### Actions

#### Development Phase

- [ ] Create a security review checklist covering:
  - [ ] Authorization logic
  - [ ] Authentication integration
  - [ ] Endpoint security
  - [ ] Business logic validation
- [ ] Define review schedule and procedures.

#### Exploitation Phase

- [ ] Conduct manual security reviews once per semester or before major releases.
- [ ] Document findings and create remediation issues.
- [ ] Track and verify issue resolution.

### Responsibility

- **Development Phase:** lead dev
- **Exploitation Phase:** lead dev

### Frequency

- **Development Phase:** One-time setup
- **Exploitation Phase:**
  - Manual security reviews: twice per year (February & August)
  - Pre-release reviews: before each major release
  - Follow-up on findings: within 2 weeks of review
  - Issue resolution: according to severity (critical: 1 week, high: 1 month)

### Validation

- Produce a short summary report of findings after each review.
- Track remediation via issues.

### Failure Handling

- If significant issues are identified:
  - Address before additional releases
  - Update test coverage and documentation as needed

---

## 6. Container Security (OpenShift Deployment)

### Objective

Reduce the risk of vulnerabilities and misconfigurations in container images deployed on the OpenShift platform, within the responsibility boundaries of the application development team.

### Mitigation Measures

- Use minimal and trusted base images for all application containers.
- Avoid including unnecessary packages, tools, or debugging utilities in container images.
- Ensure containers do not require root privileges and are compatible with OpenShift Security Context Constraints (SCCs).
- Do not embed secrets or credentials in container images; rely on OpenShift-provided secrets and configuration mechanisms.
- Regularly scan container images for known vulnerabilities as part of the CI/CD pipeline.

### Actions

#### Development Phase

- [x] Review and document the base images used for backend and frontend containers. — [`backend/Dockerfile`](https://github.com/EPFL-ENAC/co2-calculator/blob/dev/backend/Dockerfile), [`frontend/Dockerfile`](https://github.com/EPFL-ENAC/co2-calculator/blob/dev/frontend/Dockerfile)
- [x] Enforce non-root execution in Dockerfiles (e.g. avoid `USER root`). — [`backend/Dockerfile`](https://github.com/EPFL-ENAC/co2-calculator/blob/dev/backend/Dockerfile) runs `USER appuser`; [`frontend/Dockerfile`](https://github.com/EPFL-ENAC/co2-calculator/blob/dev/frontend/Dockerfile) uses `nginx-unprivileged`
- [x] Integrate automated container image vulnerability scanning in CI (e.g. Trivy or equivalent). — [`deploy.yml`](https://github.com/EPFL-ENAC/co2-calculator/blob/dev/.github/workflows/deploy.yml), [`image-vulnerability-scan.yml`](https://github.com/EPFL-ENAC/co2-calculator/blob/dev/.github/workflows/image-vulnerability-scan.yml)
- [x] Configure CI to fail builds when critical container vulnerabilities are detected. — [`deploy.yml`](https://github.com/EPFL-ENAC/co2-calculator/blob/dev/.github/workflows/deploy.yml) sets `skip_vulnerability_scan: false` — HIGH/CRITICAL block the push
- [ ] Test containers under OpenShift Security Context Constraints.

#### Exploitation Phase

- [ ] Monitor container scan results on each build.
- [ ] Update base images when vulnerabilities are detected.
- [ ] Verify containers run successfully in OpenShift environment.
- [ ] Periodically review and update container configurations.

### Responsibility

- **Development Phase:** lead dev
- **Exploitation Phase:** code reviewer
- **Out of scope:** OpenShift cluster configuration and runtime security enforcement

### Frequency

- **Development Phase:** One-time setup
- **Exploitation Phase:**
  - Container scans: on every image build (automated)
  - Base image updates: monthly or when vulnerabilities detected
  - Critical vulnerabilities: within 24 hours
  - High vulnerabilities: within 1 week
  - Configuration review: quarterly

### Validation

- Verify that container images build and run successfully under OpenShift SCC constraints.
- Review CI logs to confirm container scans are executed on each build.
- Periodically review scan reports for unresolved high or critical vulnerabilities.
- Confirm that no secrets are present in container images or Dockerfiles.

### Failure Handling

- If critical vulnerabilities are detected in a container image:
  - Block the release until the issue is resolved or mitigated.
  - Update base images or dependencies as required.
- If containers fail to run under OpenShift security constraints:
  - Treat as a configuration error.
  - Modify image configuration to comply with non-root and restricted execution requirements.

---

## 7. Security Documentation

### Objective

Maintain comprehensive and up-to-date security documentation to ensure compliance with security requirements, facilitate knowledge transfer, and support incident response.

### Mitigation Measures

- Document all security-related procedures, architectures, and processes.
- Keep documentation current and accessible to team members.
- Document compliance with legal, regulatory, and contractual security requirements.
- Maintain documentation for incident response, business continuity, and change management.

### Required Documentation

All ten are indexed, with their current state, in
[Security Documentation Index](../architecture/security-documentation.md).

1. **Encryption Keys Management**
   - Technical and organizational measures to guarantee availability, confidentiality, and integrity of encryption keys used in the codebase (if applicable)
   - Delivered: [Encryption and Key Management](../architecture/encryption.md) — also answers the transfer-encryption requirement and records the known gaps

2. **Operating Procedures**
   - Document security procedures, keep them updated, and make them available to team members

3. **Change Management Procedures**
   - Procedures for managing changes to code, data processing systems, and methods

4. **Malicious Code Detection and Prevention**
   - Detection, prevention, and restore systems designed to protect against malicious code (automated scans, review processes)

5. **Technical Vulnerability Monitoring**
   - Monitoring process for managing technical vulnerabilities, including backdoors, in software and systems used

6. **Third-Party List**
   - List of third parties (dependencies, libraries, external services) involved in the service

7. **Incident Response Procedures**
   - Procedures for responding to security incidents rapidly and effectively
   - Must specify how and under what timeframe incidents will be communicated
   - Required level of confidentiality for communications

8. **Business Continuity Plan**
   - Business continuity plan that includes IT security aspects

9. **Service Maintenance and Restore Procedures**
   - Procedures for maintaining and restoring the service
   - Ensuring availability of information within agreed timeframes

10. **Compliance Procedures**
    - Procedures for complying with legal, regulatory, and contractual requirements
    - Meeting specific security needs

### Actions

#### Development Phase

- [x] Create documentation structure and templates. — [Documentation standards](../architecture/documentation-standards.md)
- [x] Document current authentication/authorization architecture. — [Auth flow](../architecture/04-auth-flow.md), [ADR-012](012-jwt-authentication-strategy.md)
- [x] Document encryption in transfer and encryption key management. — [Encryption and Key Management](../architecture/encryption.md)
- [ ] Create incident response procedure document.
- [x] Document change management process. — [Guardrails § Workflow](../contributing/guardrails.md), [Release management](../architecture/release-management.md)
- [x] Create security requirements compliance checklist. — [EPFL compliance mapping](../architecture/epfl-compliance-mapping.md), this ADR
- [x] Document all third-party dependencies. — [Security documentation index § Third parties](../architecture/security-documentation.md#third-parties)
- [x] Establish documentation ownership and review schedule. — [Security documentation index § Ownership](../architecture/security-documentation.md#ownership-and-review-cadence)

#### Exploitation Phase

- [ ] Update documentation when changes occur:
  - [ ] Authentication/authorization modifications
  - [ ] New third-party dependencies
  - [ ] Security procedure changes
  - [ ] Architecture or design changes
- [ ] Maintain incident log with resolutions and lessons learned.
- [ ] Review and update third-party dependencies list quarterly.
- [ ] Update compliance documentation as requirements change.
- [ ] Conduct annual comprehensive documentation review.
- [ ] Ensure documentation is accessible to all team members.
- [ ] Update documentation after each security incident or major change.

### Responsibility

- **Development Phase:** lead dev
- **Exploitation Phase:** project manager

### Frequency

- **Development Phase:** One-time creation
- **Exploitation Phase:**
  - Documentation updates: within 1 week of relevant changes
  - Third-party dependencies list: quarterly review (January, April, July, October)
  - Comprehensive documentation audit: annually (every January)
  - Incident response documentation: within 1 week after incident resolution
  - Compliance documentation: before each major release

### Validation

- Verify documentation reflects current implementation.
- Ensure new team members can understand security procedures from documentation.
- Confirm all required documentation items are present and current.
- Validate that incident response procedures are documented with clear timeframes.
- Check that third-party list is complete and up-to-date.

### Failure Handling

- If documentation is outdated or incomplete:
  - Schedule immediate update session.
  - Assign responsibility for specific sections.
  - Set deadline for completion.
- If documentation is not accessible:
  - Ensure proper permissions are set.
  - Communicate location to all team members.
- If compliance gaps are identified:
  - Document the gap immediately.
  - Create action plan to address.
  - Escalate to project manager.

---

## 8. Verification log

Every ticked box above carries its own evidence inline — a file, a
workflow, or a named test. A box with no reference next to it has not
been verified, and should not be ticked.

Last full pass: **2026-08-24**.

Still open, with the reason:

- **Incident response timeframes and confidentiality level** — the
  procedure exists but states neither, and the requirement asks for
  both by name.
- **Recovery objectives are best-effort, not agreed** — see
  [Security documentation index § Recovery objectives](../architecture/security-documentation.md#recovery-objectives).
  Detection is measured; database restore depends on EPFL DSI, and
  deleted objects are not recoverable.

Every remaining Exploitation Phase box is a recurring process, not a
one-time task. They are tracked by the cadence table in the
[Security Documentation Index](../architecture/security-documentation.md#ownership-and-review-cadence),
not by ticking them here.

## 9. Links

- [Security documentation repo](https://github.com/EPFL-ENAC/co2-calculator-security-doc)
- [Workflow schedule](https://github.com/marketplace/actions/schedule-workflow)
- [GitHub secret scanning](https://docs.github.com/en/code-security/concepts/secret-security/about-secret-scanning)
- [SonarCloud](https://sonarcloud.io)
