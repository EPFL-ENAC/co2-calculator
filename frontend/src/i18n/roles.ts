import { ROLES } from 'src/constant/roles';

// Single source of truth for role display names and descriptions.
// Names are keyed by the role string so `$t(role)` resolves directly.
export default {
  [ROLES.StandardUser]: {
    en: 'Standard User',
    fr: 'Utilisateur Standard',
  },
  [ROLES.PrincipalUser]: {
    en: 'Principal User',
    fr: 'Utilisateur Principal',
  },
  [ROLES.BackOfficeMetier]: {
    en: 'Back-Office Standard',
    fr: 'Back-Office Standard',
  },
  [ROLES.SuperAdmin]: {
    en: 'Back-Office Admin',
    fr: 'Back-Office Admin',
  },
  role_standard_description: {
    en: 'Unit member with access to their own travel and cloud/AI module entries',
    fr: 'Membre d’unité ayant accès à ses propres saisies des modules déplacements et cloud/IA',
  },
  role_principal_description: {
    en: 'Unit manager with full access to all modules for their unit, and can assign Standard User roles',
    fr: 'Responsable d’unité avec accès complet à tous les modules de son unité, et pouvant attribuer le rôle Utilisateur Standard',
  },
  role_backoffice_description: {
    en: 'Day-to-day back-office operations: reporting, user management, documentation',
    fr: 'Opérations courantes du back-office : reporting, gestion des utilisateurs, documentation',
  },
  role_superadmin_description: {
    en: 'Full back-office access including sensitive configuration and pipeline controls',
    fr: 'Accès complet au back-office, y compris la configuration sensible et les contrôles du pipeline',
  },
} as const;
