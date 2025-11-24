export interface SidebarNavItem {
  routeName: string;
  icon: string;
  description?: string;
}

export const BACKOFFICE_NAV: Record<string, SidebarNavItem> = {
  BACKOFFICE_REPORTING: {
    routeName: 'backoffice-reporting',
    description: 'backoffice-reporting-description',
    icon: 'o_assessment',
  },
  BACKOFFICE_USER_MANAGEMENT: {
    routeName: 'backoffice-user-management',
    description: 'backoffice-user-management-description',
    icon: 'o_people',
  },
  BACKOFFICE_DATA_MANAGEMENT: {
    routeName: 'backoffice-data-management',
    description: 'backoffice-data-management-description',
    icon: 'data_object',
  },
  BACKOFFICE_DOCUMENTATION_EDITING: {
    routeName: 'backoffice-documentation-editing',
    description: 'backoffice-documentation-editing-description',
    icon: 'o_edit_document',
  },
};

export const SYSTEM_NAV: Record<string, SidebarNavItem> = {
  SYSTEM_USER_MANAGEMENT: {
    routeName: 'system-user-management',
    description: 'system-user-management-description',
    icon: 'o_people',
  },
  SYSTEM_MODULE_MANAGEMENT: {
    routeName: 'system-module-management',
    description: 'system-module-management-description',
    icon: 'o_view_module',
  },
  SYSTEM_LOGS: {
    routeName: 'system-logs',
    description: 'system-logs-description',
    icon: 'o_list_alt',
  },
};
