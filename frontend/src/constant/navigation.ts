export interface NavItem {
  routeName: string;
  icon: string;
  description?: string;
  limitedAccess?: boolean;
  superAdminOnly?: boolean;
}

export const BACKOFFICE_NAV: Record<string, NavItem> = {
  BACKOFFICE_REPORTING: {
    routeName: 'backoffice-reporting',
    description: 'backoffice-reporting-description',
    icon: 'o_assessment',
  },
  BACKOFFICE_USER_MANAGEMENT: {
    routeName: 'backoffice-user-management',
    description: 'backoffice-user-management-description',
    icon: 'o_people',
    limitedAccess: true,
  },
  BACKOFFICE_DOCUMENTATION_EDITING: {
    routeName: 'backoffice-documentation-editing',
    description: 'backoffice-documentation-editing-description',
    icon: 'o_edit_document',
  },
  BACKOFFICE_UI_TEXTS_EDITING: {
    routeName: 'backoffice-ui-texts-editing',
    description: 'backoffice-ui-texts-editing-description',
    icon: 'o_edit_document',
  },
  BACKOFFICE_DATA_MANAGEMENT: {
    routeName: 'backoffice-data-management',
    description: 'backoffice-data-management-description',
    icon: 'data_object',
    limitedAccess: true,
  },
  BACKOFFICE_LOGS: {
    routeName: 'backoffice-logs',
    description: 'backoffice-logs-description',
    icon: 'o_list_alt',
    superAdminOnly: true,
  },
};
