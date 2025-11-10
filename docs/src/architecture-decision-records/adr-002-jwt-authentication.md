# ADR-002: Adopt JWT-based Authentication

## Status

Accepted

## Context

We needed to implement an authentication mechanism for our distributed system that would:

- Support stateless authentication across multiple services
- Work well with our chosen frontend framework (Vue.js)
- Integrate with our identity provider (Microsoft Entra ID)
- Provide secure token-based authentication
- Minimize server-side session storage requirements

## Decision

We will use JSON Web Tokens (JWT) for authentication across our system.

## Rationale

JWT provides several benefits for our distributed architecture:

1. **Stateless Authentication**: JWT tokens contain all necessary user information, eliminating the need for server-side session storage
2. **Cross-Origin Support**: Works well with SPAs and CORS scenarios
3. **Standard Format**: Well-established standard (RFC 7519) with broad industry adoption
4. **Microservices Friendly**: No shared session store required between services
5. **Mobile Ready**: Suitable for mobile applications and API clients
6. **Integration with OIDC**: Works seamlessly with OpenID Connect providers like Microsoft Entra ID

Compared to session-based authentication:

- No server-side storage requirements for session data
- Better scalability for distributed systems
- Simpler to implement in microservices architecture

## Consequences

### Positive

- Improved scalability due to stateless nature
- Reduced server-side storage requirements
- Simplified authentication in microservices architecture
- Better support for mobile and API clients
- Industry-standard approach with good tooling support

### Negative

- Larger token size compared to session IDs
- Tokens cannot be easily revoked before expiration (without additional mechanisms)
- Sensitive information must not be stored in tokens
- Requires careful token expiration and refresh strategies

## Implementation Details

Our JWT implementation will include:

1. **Token Types**:
   - ID Tokens: For user identification
   - Access Tokens: For API authorization
   - Refresh Tokens: For session continuity (optional)

2. **Token Validation**:
   - Signature verification using public keys from Microsoft Entra ID
   - Expiration checking
   - Audience validation

3. **Security Measures**:
   - HTTPS-only transmission
   - Secure storage in HTTP-only cookies or local storage
   - Short-lived access tokens with optional refresh mechanism

## References

- [JWT.IO](https://jwt.io/)
- [RFC 7519](https://tools.ietf.org/html/rfc7519)
- [Microsoft Entra ID Documentation](https://learn.microsoft.com/en-us/azure/active-directory/)
