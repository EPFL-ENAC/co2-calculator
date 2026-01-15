export const ROLES = {
  PrincipalUser: 'co2.user.principal',
  StandardUser: 'co2.user.std',
  BackOfficeMetier: 'co2.backoffice.metier',
  SuperAdmin: 'co2.superadmin',
} as const;

export type Roles = (typeof ROLES)[keyof typeof ROLES];

export const ROLES_LIST: Roles[] = Object.values(ROLES);
