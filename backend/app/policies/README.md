# Open Policy Agent Policies

This directory contains Rego policy files for authorization decisions.

## Policy Files

### `resource_policy.rego`

Defines authorization rules for CO2 calculator resources.

**Key Concepts:**

1. **Actions**: `read`, `create`, `update`, `delete`
2. **Roles**:
   - `admin` - Full access to resources in their unit
   - `unit_admin` - Manage unit resources
   - `resource.create` - Permission to create resources
3. **Visibility Levels**:
   - `public` - Accessible to all authenticated users
   - `unit` - Accessible to users in the same unit
   - `private` - Accessible only to the owner

**Policy Rules:**

- **List Resources**: Returns filters to apply to database queries
- **Read Resource**: Checks if user can view a specific resource
- **Create Resource**: Validates user can create resources in a unit
- **Update Resource**: Checks ownership or admin permissions
- **Delete Resource**: Checks ownership or admin permissions

## Testing Policies Locally

You can test policies using the OPA CLI:

```bash
# Install OPA
brew install opa

# Test a policy
opa test app/policies/

# Run OPA server
# opa run --server --addr :8181 app/policies/
```

## Example OPA Queries

### List Resources for a User

```bash
curl -X POST http://localhost:8181/v1/data/authz/resource/list \
  -H "Content-Type: application/json" \
  -d '{
    "input": {
      "action": "read",
      "resource_type": "resource",
      "user": {
        "id": "user@example.com",
        "roles": ["user"],
        "unit_id": "ENAC",
        "is_superuser": false
      }
    }
  }'
```

### Check Read Permission

```bash
curl -X POST http://localhost:8181/v1/data/authz/resource/read \
  -H "Content-Type: application/json" \
  -d '{
    "input": {
      "action": "read",
      "user": {
        "id": "user@example.com",
        "roles": ["user"],
        "unit_id": "ENAC"
      },
      "resource": {
        "id": 123,
        "owner_id": "owner@example.com",
        "unit_id": "ENAC",
        "visibility": "unit"
      }
    }
  }'
```

## Integration with FastAPI

The OPA client (`app/core/opa_client.py`) queries these policies via HTTP:

```python
decision = query_opa("authz/resource/list", {
    "action": "read",
    "user": {"id": user.id, "roles": user.roles}
})

if decision["allow"]:
    filters = decision.get("filters", {})
    # Apply filters to database query
```

## Policy Development

When adding new policies:

1. Define clear input structure
2. Use descriptive rule names
3. Provide deny reasons for debugging
4. Test with multiple scenarios
5. Document the policy logic
