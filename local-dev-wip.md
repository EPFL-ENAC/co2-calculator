# Local Development - No info on:

How to run the project locally -> should run via docker-compose + Makefile
-> uv for python / npm for frontend
Database setup/migrations --> use alembic for python
Environment variables (.env setup) -> .env.example should be present and documented
How to access dev environment locally -> the dev environment should run diurectgly via make run


# Debugging & Troubleshooting - No guidance on: ok, let's add some

Common issues and solutions
How to debug
Logs location
Who to contact for technical issues
Dependencies Management - Missing:

# How to add new dependencies
Version pinning policy: HARD versionning
Upgrade strategy: only on security issues
Breaking Changes - No policy on: ? not sure

# How to handle breaking changes
Migration guides documented in the MIGRATION.md for each version with dowgrade and upgrade scripts.js
Deprecation process

# Communication Channels - Limited info on: email that's it

Where to ask questions (Slack, Teams, email?) (email)
Meeting schedules: nope
Who owns what components nope

# Issue Labels/Templates - Not documented:
Go wild on this one, but limit the number of label and prio level
What labels mean
Priority levels
Issue lifecycle

# Release Process - Missing details on:

Versioning scheme (SemVer?) SEMVVER
Changelog maintenance: automatica via release-please gituhub workflow
Release notes process: automatic

# Emergency/Hotfix Process - No info on: hotfix branch

How to handle critical bugs in production
Fast-track approval process: ok we could add

# First-Time Contributors - Could add:

"Good first issue" guidance
Mentorship information
Recognition/acknowledgment
Financial Contribution section - Has no contact or next steps


We should follow rfc 

## Part I: The RFC-First Process

### When Ideas Need Community Input

Use RFCs for substantial changes:
- New features affecting multiple teams
- Architectural decisions with system-wide impact  
- Changes to development processes or standards
- API modifications or new public interfaces
- Database schema changes
- Security or compliance implementations

Skip RFCs for routine work:
- Bug fixes that don't change interfaces or behavior
- Code structure improvements (extracting functions, renaming variables, optimizing algorithms)
- Documentation updates and corrections
- Minor dependency updates with no breaking changes
- Adding logging, metrics, or debugging tools
- Performance optimizations that don't change APIs

**Borderline cases requiring judgment**:
- Major version dependency upgrades (may need RFC if breaking changes affect other services)
- Adding new function parameters or return fields (RFC if used by other services)
- Database schema additions (RFC if other services access the data)
- Configuration changes (RFC if they affect service behavior externally)

### The RFC Lifecycle

#### 1. Problem Definition
Start with a clear problem statement and initial solution concept. Use this AI prompt pattern:

```
Help me draft an RFC for [problem description]. 
Structure it with:
- Problem statement with business impact
- High-level solution approach
- Key alternatives considered
- Areas needing community input

Focus on WHY we need this change and WHAT we want to achieve, 
not HOW to implement it yet.
```

#### 2. Community Discussion
Post the RFC for team review. Use threaded discussions to explore:
- Alternative approaches
- Integration challenges  
- Resource requirements
- Success criteria
- Implementation concerns

#### 3. Consensus Building
Work toward agreement on:
- The problem is worth solving
- The proposed approach is sound
- Implementation strategy is feasible
- Success metrics are clear

#### 4. Specification Generation
Once consensus emerges, transition to SDD:

```
Based on the approved RFC [link], create a detailed executable specification including:
- Complete user stories with acceptance criteria
- Technical architecture decisions
- Data models and API contracts
- Testing scenarios and success metrics
- Implementation phases

Ensure the specification captures all RFC agreements and can generate working code.
```

### RFC Templates via AI

Instead of complex RFC management tools, use AI with this prompt template:

```
Create an RFC using this format:

# RFC: [Title]
**Status**: Draft | Under Review | Accepted | Rejected  
**Author(s)**: [Names]  
**Created**: [Date]

## Problem Statement
What business or technical problem are we solving? Include impact and urgency.

## Proposed Solution
High-level approach without implementation details. Focus on user value and business outcomes.

## Alternatives Considered
Other approaches evaluated and why they were rejected.

## Implementation Strategy
General technical approach, key decisions, and phasing plan.

## Success Criteria
How will we measure if this RFC achieves its goals?

## Community Input Needed
Specific questions or concerns requiring team expertise.

## Open Questions
Unresolved issues for discussion.
```
