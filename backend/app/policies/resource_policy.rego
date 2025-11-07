# Resource Authorization Policy
#
# This policy defines authorization rules for CO2 calculator resources.
# It implements a hierarchical permission model based on:
# - User roles (co2.user.*, co2.backoffice.*, co2.service.mgr)
# - Unit membership
# - Resource visibility (public, private, unit)
# - Resource ownership

package authz.resource

import future.keywords.if
import future.keywords.in

# Default deny
default allow = false

# ============================================================================
# LIST Resources - Determine which resources a user can see
# ============================================================================

# System IT administrators (service managers) can do anything
allow if {
    "co2.service.mgr" in input.user.roles
}

# Superusers can see all resources (legacy flag)
allow if {
    input.action == "read"
    input.user.is_superuser == true
}

# Back office full admins can see all resources (no filters)
allow if {
    input.action == "read"
    "co2.backoffice.admin" in input.user.roles
    filters := {}
}

# Unit-scoped admins/managers (principal, secondary, backoffice.std, legacy admin/unit_admin)
allow if {
    input.action == "read"
    has_admin_role
    not ("co2.backoffice.admin" in input.user.roles)
}

# Regular users can see:
# 1. Public resources
# 2. Resources in their unit with "unit" visibility
# 3. Their own resources
list if {
    input.action == "read"
}

# Filters for regular users
filters := {
    "visibility": ["public", "unit"],
    "unit_id": input.user.unit_id
} if {
    input.action == "read"
    not input.user.is_superuser
    not has_admin_role
    not ("co2.backoffice.admin" in input.user.roles)
    not ("co2.service.mgr" in input.user.roles)
}

# Filters for superusers (no filters = see all)
filters := {} if {
    input.action == "read"
    input.user.is_superuser
}

filters := {} if {
    input.action == "read"
    "co2.service.mgr" in input.user.roles
}

# Filters for unit-scoped admins
filters := {
    "unit_id": input.user.unit_id
} if {
    input.action == "read"
    has_admin_role
    not input.user.is_superuser
    not ("co2.backoffice.admin" in input.user.roles)
    not ("co2.service.mgr" in input.user.roles)
}

# Helper: Check if user has admin role
has_admin_role if { "admin" in input.user.roles }                # legacy
has_admin_role if { "unit_admin" in input.user.roles }           # legacy
has_admin_role if { "co2.user.principal" in input.user.roles }
has_admin_role if { "co2.user.secondary" in input.user.roles }
has_admin_role if { "co2.backoffice.std" in input.user.roles }

# ============================================================================
# READ Single Resource
# ============================================================================

# Superusers can read any resource
allow if {
    input.action == "read"
    input.resource
    input.user.is_superuser == true
}

# Users can read their own resources
allow if {
    input.action == "read"
    input.resource
    input.resource.owner_id == input.user.id
}

# Users can read public resources
allow if {
    input.action == "read"
    input.resource
    input.resource.visibility == "public"
}

# Users can read unit resources if they're in the same unit
allow if {
    input.action == "read"
    input.resource
    input.resource.visibility == "unit"
    input.resource.unit_id == input.user.unit_id
}

# Admins can read all resources in their unit
allow if {
    input.action == "read"
    input.resource
    has_admin_role
    input.resource.unit_id == input.user.unit_id
}

# ============================================================================
# CREATE Resource
# ============================================================================

# Users with "resource.create" role can create resources
allow if {
    input.action == "create"
    "resource.create" in input.user.roles
}

# Users can create resources in their own unit
allow if {
    input.action == "create"
    input.resource_data
    input.resource_data.unit_id == input.user.unit_id
}

# Admins can create resources in their unit
allow if {
    input.action == "create"
    has_admin_role
    input.resource_data.unit_id == input.user.unit_id
}

# Superusers can create resources anywhere
allow if {
    input.action == "create"
    input.user.is_superuser == true
}


allow if {
    "co2.service.mgr" in input.user.roles
    input.action == "create"
}

allow if {
    "co2.service.mgr" in input.user.roles
    input.action == "update"
}

allow if {
    "co2.service.mgr" in input.user.roles
    input.action == "delete"
}

# ============================================================================
# UPDATE Resource
# ============================================================================

# Superusers can update any resource
allow if {
    input.action == "update"
    input.resource
    input.user.is_superuser == true
}

# Users can update their own resources
allow if {
    input.action == "update"
    input.resource
    input.resource.owner_id == input.user.id
}

# Admins can update resources in their unit
allow if {
    input.action == "update"
    input.resource
    has_admin_role
    input.resource.unit_id == input.user.unit_id
}

# ============================================================================
# DELETE Resource
# ============================================================================

# Superusers can delete any resource
allow if {
    input.action == "delete"
    input.resource
    input.user.is_superuser == true
}

# Users can delete their own resources
allow if {
    input.action == "delete"
    input.resource
    input.resource.owner_id == input.user.id
}

# Admins can delete resources in their unit
allow if {
    input.action == "delete"
    input.resource
    has_admin_role
    input.resource.unit_id == input.user.unit_id
}

# ============================================================================
# Deny reason (for debugging)
# ============================================================================

reason := "User is not authenticated" if {
    not input.user
}

reason := "Insufficient permissions" if {
    input.user
    not allow
}
