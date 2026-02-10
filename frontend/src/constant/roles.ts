export const ROLES = {
  PrincipalUser: 'calco2.user.principal',
  StandardUser: 'calco2.user.standard',
  BackOfficeMetier: 'calco2.backoffice.metier',
  SuperAdmin: 'calco2.superadmin',
} as const;

export type Roles = (typeof ROLES)[keyof typeof ROLES];

export const ROLES_LIST: Roles[] = Object.values(ROLES);
