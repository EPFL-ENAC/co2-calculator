// A priori used by login-test to list the available roles
// should use openapi types instead for idempotency
export const ROLES = {
  PrincipalUser: 'calco2.user.principal',
  StandardUser: 'calco2.user.standard',
  BackOfficeMetier: 'calco2.backoffice.metier',
  SuperAdmin: 'calco2.backoffice.admin',
} as const;

export type Roles = (typeof ROLES)[keyof typeof ROLES];

export const ROLES_LIST: Roles[] = Object.values(ROLES);
