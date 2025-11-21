export const ROLES = {
  PrincipalUser: 'co2.user.principal',
  SecondaryUser: 'co2.user.secondary',
  StandardUser: 'co2.user.std',
  BackOfficeAdmin: 'co2.backoffice.admin',
  BackOfficeStandard: 'co2.backoffice.std',
  System: 'co2.service.mgr',
} as const;

export type Roles = (typeof ROLES)[keyof typeof ROLES];

export const ROLES_LIST: Roles[] = Object.values(ROLES);
