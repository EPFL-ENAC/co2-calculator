import { matDataObject } from '@quasar/extras/material-icons';
import {
  outlinedAssessment,
  outlinedPeople,
  outlinedEditNote,
  outlinedListAlt,
  outlinedAccountTree,
} from '@quasar/extras/material-icons-outlined';

export interface NavItem {
  routeName: string;
  icon: string;
  description?: string;
}

// Presentation only. A page's permission gate lives in its route `meta`
// (`requiredPermission`/`requiredAction` in router/routes.ts) — the single
// source of truth shared by the router guard and the back-office sidebar.
export const BACKOFFICE_NAV: Record<string, NavItem> = {
  BACKOFFICE_REPORTING: {
    routeName: 'backoffice-reporting',
    description: 'backoffice-reporting-description',
    icon: outlinedAssessment,
  },
  BACKOFFICE_USER_MANAGEMENT: {
    routeName: 'backoffice-user-management',
    description: 'backoffice-user-management-description',
    icon: outlinedPeople,
  },
  BACKOFFICE_DOCUMENTATION_EDITING: {
    routeName: 'backoffice-documentation-editing',
    description: 'backoffice-documentation-editing-description',
    icon: outlinedEditNote,
  },
  BACKOFFICE_UI_TEXTS_EDITING: {
    routeName: 'backoffice-ui-texts-editing',
    description: 'backoffice-ui-texts-editing-description',
    icon: outlinedEditNote,
  },
  BACKOFFICE_DATA_MANAGEMENT: {
    routeName: 'backoffice-data-management',
    description: 'backoffice-data-management-description',
    icon: matDataObject,
  },
  BACKOFFICE_LOGS: {
    routeName: 'backoffice-logs',
    description: 'backoffice-logs-description',
    icon: outlinedListAlt,
  },
  BACKOFFICE_PIPELINE_OPERATIONS: {
    routeName: 'backoffice-pipeline-operations',
    description: 'backoffice-pipeline-operations-description',
    icon: outlinedAccountTree,
  },
};
