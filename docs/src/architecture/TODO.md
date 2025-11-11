# Architecture Documentation TODO

This document tracks remaining work needed to complete the architecture
documentation. Focus on practical developer and operations needs.

## 📊 Progress Summary

**Last Updated**: November 11, 2025
**Next Priority**: Complete local development, deployment, and monitoring
documentation.

---

**Guidelines**:

- Avoid duplicating content across files
- Review files in architecture/ folder to ensure relevance
- Follow technical writing guidelines below

---

## 🚨 Mandatory Documentation Structure Requirements

These requirements MUST be enforced to maintain consistency and avoid duplication:

### 2. Numbered File Naming Convention

**Rule**: ALL documentation files should be prefixed with a two-digit number (01-, 02-, etc.) for consistent ordering and clarity.

**Rationale**: Numbered prefixes ensure predictable file ordering in directory listings and make the documentation hierarchy explicit.

**Current Status**: ⚠️ Partially implemented (architecture/01-15 numbered, but other files lack numbers)

**Required Actions**:

- [ ] Ensure subsystem folders use `01-overview.md` naming
- [ ] Review architecture/ folder non-numbered files (cicd-workflows.md, code-standards.md, epfl-compliance-mapping.md, epfl-constraint.md, release-management.md, rfc-first-process.md, spec.md, workflow-guide.md)
- [ ] Decide: integrate into existing numbered files (01-15) or assign new numbers (16+)
- [ ] Rename or consolidate unnumbered files according to decision

### 3. Complete mkdocs.yml Navigation Coverage

**Rule**: EVERY file in the documentation (architecture/, backend/, frontend/, database/, infra/, architecture-decision-records/) MUST be properly referenced in mkdocs.yml nav section.

**Rationale**: If a file isn't in mkdocs.yml, it won't appear in the published documentation website, making it effectively invisible to users.

**Current Status**: ⚠️ Some files referenced, but inconsistent with actual file structure

**Required Actions**:

- [ ] Audit all .md files in docs/src/ directory tree
- [ ] Verify each file has a corresponding entry in mkdocs.yml nav section
- [ ] Remove mkdocs.yml entries for deleted/consolidated files
- [ ] Add missing entries for any orphaned documentation files
- [ ] Ensure nav structure mirrors the actual file hierarchy

### 4. Zero Content Duplication

**Rule**: Information should exist in EXACTLY ONE place. Use cross-references and links instead of copying content.

**Rationale**: Duplicated content creates maintenance burden and inconsistency. When information changes, all duplicates must be updated or they become incorrect.

**Current Status**: ❌ Significant duplication exists between architecture/ and subsystem folders

**Duplication Examples Found**:

- Backend technology stack described in both architecture/09-component-breakdown.md and backend/index.md
- API interface patterns duplicated in architecture/ and backend/api.md
- Testing strategies repeated across architecture/ and subsystem testing.md files
- Deployment information scattered across architecture/, backend/deploy.md, frontend/deploy.md

**Required Actions**:

- [ ] Audit all documentation for duplicated content
- [ ] Establish clear content ownership: architecture/ = system-wide, subsystems/ = implementation-specific
- [ ] Remove duplicated tech stack descriptions from subsystem files
- [ ] Replace duplicated content with cross-references: "See [Architecture Overview](../architecture/09-component-breakdown.md) for details"
- [ ] Document content boundaries: what belongs in architecture/ vs. what belongs in subsystem folders

### 5. Single Source of Truth Hierarchy

**Rule**: Follow this information hierarchy for content placement:

1. **architecture/** - System-wide design, technology decisions, component interactions
2. **architecture-decision-records/** - Historical decision records (ADRs)
3. **backend/01-overview.md** - Backend-specific implementation details, setup, commands
4. **frontend/01-overview.md** - Frontend-specific implementation details, setup, commands
5. **database/01-overview.md** - Database-specific schema, queries, maintenance
6. **infra/01-overview.md** - Infrastructure-specific deployment, monitoring, operations

**Content Boundaries**:

- Architecture folder should NOT contain implementation commands (those go in subsystem folders)
- Subsystem folders should NOT repeat technology choices (those are in architecture/)
- Cross-cutting concerns (auth, logging, security) belong in architecture/13-cross-cutting-concerns.md
- Historical decisions belong in ADRs, not in multiple doc locations

---

## 🧠 Technical Writing Guidelines

### Structure & Style

- Start with a **clear title under 60 characters**
- **Capitalize** the title (no all caps, no punctuation at end)
- **Separate** the title from the body with a blank line
- Begin with a short **context paragraph** — what this covers and why it matters
- Use **imperative mood** (“Add configuration option”, “Describe API flow”)
- **Use active voice** — “Run the command”, not “The command is run”
- Keep sentences **under 20 words** whenever possible
- **Wrap text at 72 characters** for readability in terminals and diffs
- **Prefer clarity over cleverness** — use simple, direct language
- **Avoid filler words** like “simply”, “basically”, or “clearly”
- **Be consistent** with terminology and capitalization
- **Use code blocks** for commands or snippets, not inline text
- **Add examples** after explaining a concept
- **Use lists** (numbered for steps, bullets for unordered info)
- **Use headers every 2–3 paragraphs** to reset focus
- **Add a TL;DR or summary** for long sections

---

### Length & Focus

- Aim for **500–800 words** or roughly **40–60 lines** per document
- Each section should be **readable in under 5 minutes**
- If it exceeds one screen scroll, **split it into multiple docs or appendices**
- Use **visual breaks** (tables, bullets, code examples) every 20 lines
- For longer pieces, include a **summary per section**

---

### Document Types

| Type                     | Target Length | Notes                            |
| ------------------------ | ------------- | -------------------------------- |
| **README / How-to**      | 30–60 lines   | Enough for setup + quick context |
| **Design Doc / ADR**     | 40–80 lines   | One decision per document        |
| **Troubleshooting Note** | 25–50 lines   | One issue, one resolution        |
| **Technical Proposal**   | 60–120 lines  | Use sections and summaries       |

---

### Final Check

Before sharing, make sure the document:

- Explains **what and why**, not just **how**
- Do NOT **duplicate** information of other files
- Can be **understood in one uninterrupted sitting (~10 min)**
- Has a **clear takeaway or action** at the end
- Would make sense if **read in isolation**

---

## 🟡 Remaining Work

### Documentation Structure Enforcement (MANDATORY - HIGH PRIORITY)

**Priority**: MUST complete before other documentation work

26. **Standardize File Naming with Numbers**
    - [ ] Review architecture/ unnumbered files and assign appropriate numbers or consolidate:
      - [ ] cicd-workflows.md (possibly merge into 06-cicd-pipeline.md?)
      - [ ] code-standards.md (merge into 07-global-conventions.md?)
      - [ ] epfl-compliance-mapping.md (keep as 16-epfl-compliance.md?)
      - [ ] epfl-constraint.md (merge into epfl-compliance-mapping.md?)
      - [ ] release-management.md (merge into 06-cicd-pipeline.md?)
      - [ ] rfc-first-process.md (merge into 15-appendices.md?)
      - [ ] spec.md (move to appendices or separate requirements folder?)
      - [ ] workflow-guide.md (merge into 06-cicd-pipeline.md?)
      - [ ] TODO.md (keep as-is, not published)
    - [ ] Rename/consolidate all identified files

27. **Update mkdocs.yml Navigation**
    - [ ] Remove entries for consolidated/deleted files
    - [ ] Add entries for all architecture/ numbered files (01-15)
    - [ ] Add entries for remaining architecture/ files after renumbering
    - [ ] Update subsystem sections to reflect single file structure
    - [ ] Verify all ADR files are properly listed
    - [ ] Test that mkdocs build completes without warnings

28. **Eliminate Content Duplication**
    - [ ] Audit architecture/09-component-breakdown.md vs. backend/frontend/database/infra index files
    - [ ] Remove duplicated technology stack descriptions from subsystem files
    - [ ] Remove duplicated API pattern descriptions
    - [ ] Remove duplicated testing strategy content
    - [ ] Remove duplicated deployment information
    - [ ] Add cross-references to architecture/ docs instead of duplicating content
    - [ ] Document in each subsystem file: "For system architecture, see [Architecture](../architecture/)"

29. **Resolve All TODO/TBD Markers**
    - [ ] Review 86+ TODO/TBD/FIXME markers found across documentation
    - [ ] Complete placeholder sections with actual content where information exists
    - [ ] Remove placeholder sections that cannot be filled yet (document in this TODO instead)
    - [ ] Ensure no "TODO: Document..." sections remain in published docs
    - [ ] Consolidate remaining work items into this TODO.md file

---

### Database Documentation

14. **Migration Strategy**
    - [ ] Document database migration procedures
    - [ ] Add version upgrade guides
    - [ ] Create breaking change documentation

### Infrastructure Documentation

15. **Monitoring Setup**
    - [ ] Document Prometheus metrics exposed by each service
    - [ ] List key Grafana dashboards and their purposes
    - [ ] Define alert thresholds and escalation procedures
    - [ ] Document SIEM integration configuration

### Development & Operations

16. **Local Development Setup**
    - [ ] Create comprehensive local development guide
    - [ ] Document Docker Compose setup steps
    - [ ] Add troubleshooting section for common dev environment issues
    - [ ] Document how to run tests locally

17. **Deployment Procedures**
    - [ ] Document step-by-step deployment process for each environment
    - [ ] Create rollback procedure documentation
    - [ ] Document blue-green deployment strategy in detail
    - [ ] Add deployment checklist

---

## 🟢 Future Enhancements

### Performance & Scalability

18. **Scalability Documentation**
    - [ ] Add load testing results and capacity planning data
    - [ ] Document autoscaling thresholds and configurations
    - [ ] Create performance benchmarks for different load scenarios
    - [ ] Document database optimization strategies

### Data Management

19. **Data Lifecycle**
    - [ ] Document data retention policies (10 years for results, 5 years for travel)
    - [ ] Create data archival strategy
    - [ ] Document GDPR compliance measures
    - [ ] Add data backup and recovery procedures

### Testing Strategy

20. **Testing Documentation**
    - [ ] Document unit testing strategy and coverage requirements (70% minimum)
    - [ ] Explain integration testing approach
    - [ ] Document E2E testing with Cypress
    - [ ] Add load testing strategy with k6/Locust

### API Documentation

21. **API Specifications**
    - [ ] Ensure OpenAPI/Swagger documentation is complete
    - [ ] Document all API versioning strategy
    - [ ] Add API deprecation policy
    - [ ] Create API usage examples for common workflows

### Project Context

22. **Functional Requirements Mapping**
    - [ ] Map architecture components to functional modules from spec.md:
      - Mon Laboratoire
      - Déplacements professionnels
      - Infrastructure
      - Consommation électrique équipement
      - Achats
      - Services internes
      - Visualisation des résultats
      - Documentation & Contact
      - Interfaces de gestion (admin)
    - [ ] Document how each layer supports the functional requirements

---

## 📋 Documentation Maintenance

23. **Cross-Reference Validation**
    - [ ] Verify all internal links work correctly
    - [ ] Ensure consistent terminology across all documents
    - [ ] Validate that referenced documents exist
    - [ ] Check that all "TO COMPLETE TAG" items are addressed

24. **Code Examples**
    - [ ] Add configuration file examples where referenced
    - [ ] Include sample API requests/responses
    - [ ] Add example environment variable files
    - [ ] Provide sample Kubernetes manifests

---
