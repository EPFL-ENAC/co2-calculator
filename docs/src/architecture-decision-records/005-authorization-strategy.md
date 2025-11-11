# ADR-005: Use In-Code RBAC, Reject OPA

**Status**: Accepted  
**Date**: 2024-12-01  
**Deciders**: Development Team, Security Lead

## TL;DR

Implement role-based access control directly in Python code.
Reject Open Policy Agent (OPA) as too complex for current needs.

## Context

Need authorization system for 6 user roles (`co2.user.std`,
`co2.user.principal`, `co2.backoffice.admin`, etc.) controlling
who can view/create/edit emission records and manage units.

Options: In-code RBAC vs external policy engine (OPA).

## Decision

**Use in-code RBAC** with `User.roles` JSON field and helper methods.

**Reject OPA** - operational complexity outweighs benefits.

**Why in-code RBAC wins:**

- Simple to implement and debug
- No external service dependency
- Zero network latency (<1ms vs 5-20ms)
- Role hierarchy sufficient for requirements
- Python-native testing (pytest)
- Fewer operational failure points

**What tipped the balance**:
@domq: "We are adopting a full Python code approach for now, even if it means revisiting this decision later if there is demand for it. Ideally, we will only rewrite the code that controls access." cf issue #16

## Alternatives Considered

**Open Policy Agent (OPA)**  
✗ Operational complexity, network calls, learn Rego, monitoring overhead  
✓ Centralized policies, runtime updates, microservices-ready

**Comparison:**

| Criterion    | In-Code RBAC  | OPA              |
| ------------ | ------------- | ---------------- |
| Latency      | <1ms          | 5-20ms           |
| Debugging    | Easy (Python) | Hard (Rego)      |
| Dependencies | None          | External service |
| Complexity   | Low           | High             |
| Team Skills  | Python        | Learn Rego       |

## Consequences

**Positive:**

- Simple implementation: `user.has_role("co2.service.mgr")`
- Zero infrastructure overhead
- Fast development (no Rego learning)
- In-memory permission checks
- Easy onboarding

**Negative:**

- Permission logic coupled to code
- Role changes require deployment
- No policy reuse across services (but no other services)
- Less centralized auditability

**Mitigation:**

- Role assignments in database (no redeploy to grant roles)
- Document role definitions clearly
- Log all permission denials

**When to reconsider OPA:**

- Multiple microservices need shared policies
- Complex attribute-based access control (ABAC)
- Compliance requires centralized policy audit trail

## Implementation

```python
class User(Base):
    roles: Mapped[List[str]] = mapped_column(JSON, default=list)

    def has_role(self, role: str) -> bool:
        return role in (self.roles or [])

    def has_any_role(self, roles: List[str]) -> bool:
        return bool(set(self.roles or []).intersection(roles))

@router.post("/resources")
async def create_resource(data: ResourceCreate, user: User = Depends(get_current_user)):
    if not user.has_any_role(["co2.user.principal", "co2.service.mgr"]):
        raise HTTPException(403, "Insufficient permissions")
    # ... create resource
```

## References

- [Our decision discussion](https://github.com/epFL-ENAC/co2-calculator/issues/16)
- [OPA Documentation](https://www.openpolicyagent.org/)
- [When to Use OPA](https://www.openpolicyagent.org/docs/latest/#when-to-use-opa)
