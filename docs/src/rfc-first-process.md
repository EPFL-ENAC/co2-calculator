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
