# ADR-012: Use JWT for Authentication

**Status**: Accepted  
**Date**: 2024-12-01 \n**Deciders**: Development Team

## TL;DR

Use JSON Web Tokens (JWT) for stateless authentication across
our SPA and future microservices. Supports OIDC integration
with Microsoft Entra ID.

## Context

Need authentication mechanism for distributed system that:

- Works with Vue.js SPA
- Supports multiple services (stateless)
- Integrates with MS Entra ID (OIDC)
- Minimizes server-side session storage

Options: JWT tokens vs session-based authentication.

## Decision

**Use JWT tokens** for authentication.

**Why JWT wins:**

- Stateless (no server-side session storage)
- Microservices-friendly (no shared session store)
- Works seamlessly with SPAs and CORS
- Standard format (RFC 7519)
- OIDC-compatible (MS Entra ID ready)
- Mobile-ready for future apps

## Alternatives Considered

**Session-Based Authentication**  
✗ Requires Redis/DB for sessions, shared store complexity, CORS issues  
✓ Easy revocation, smaller token size, server control
✗ Not part of the spec requirement

## Consequences

**Positive:**

- Improved scalability (stateless)
- No server-side session storage
- Simplified microservices authentication
- Industry-standard approach
- Good tooling support (joserfc, authlib)

**Negative:**

- Larger token size vs session IDs
- Cannot revoke tokens before expiration (without blacklist)
- _Must not store_ sensitive data in tokens
- Requires careful expiration strategy

**Mitigation:**

- Short-lived access tokens (15-60 min)
- Optional refresh tokens for session continuity
- Future|Optional: Redis blacklist for token revocation
- HTTPS-only transmission
- JWT in cookie httpOnly
- bcrypt password hashing

## Implementation

```python
# Token generation
from joserfc import jwt

def create_access_token(user: User) -> str:
    payload = {
        "sub": user.id,
        "email": user.email,
        "roles": user.roles,
        "exp": datetime.utcnow() + timedelta(minutes=30)
    }
    return jwt.encode(header, payload, secret_key)

# Token validation
@router.get("/protected")
async def protected_route(user: User = Depends(get_current_user)):
    # JWT validated by get_current_user dependency
    return {"message": f"Hello {user.email}"}
```

**Token Types:**

- Access tokens (30 min) - API authorization
- Refresh tokens (optional) - Session continuity
- ID tokens (OIDC) - User identification

## References

- [JWT.IO](https://jwt.io/)
- [RFC 7519](https://tools.ietf.org/html/rfc7519)
- [MS Entra ID](https://learn.microsoft.com/en-us/azure/active-directory/)
