export interface SidebarNavItem {
  routeName: string;
  icon: string;
}

export const BACKOFFICE_NAV: Record<string, SidebarNavItem> = {
  BACKOFFICE_USER_MANAGEMENT: {
    routeName: 'backoffice-user-management',
    icon: 'o_people',
  },
  BACKOFFICE_MODULE_MANAGEMENT: {
    routeName: 'backoffice-module-management',
    icon: 'o_dashboard',
  },
  BACKOFFICE_DOCUMENTATION_EDITING: {
    routeName: 'backoffice-documentation-editing',
    icon: 'o_edit_document',
  },
  BACKOFFICE_REPORTING: {
    routeName: 'backoffice-reporting',
    icon: 'o_assessment',
  },
};

export const SYSTEM_NAV: Record<string, SidebarNavItem> = {
  SYSTEM_USER_MANAGEMENT: {
    routeName: 'system-user-management',
    icon: 'o_people',
  },
  SYSTEM_MODULE_MANAGEMENT: {
    routeName: 'system-module-management',
    icon: 'o_dashboard',
  },
  SYSTEM_LOGS: {
    routeName: 'system-logs',
    icon: 'o_list_alt',
  },
};
