/**
 * Permission types matching backend structure from app.utils.permissions
 *
 * This module provides TypeScript types and enums for the permission system.
 * Permissions are calculated dynamically from user roles on the backend and
 * returned as a flat structure with dot-notation keys.
 */

/**
 * Available actions that can be performed on a permission resource.
 *
 * @enum {string}
 * @example
 * ```typescript
 * const action = PermissionAction.VIEW;
 * if (hasPermission(user.permissions, 'modules.headcount', action)) {
 *   // User can view headcount module
 * }
 * ```
 */
export enum PermissionAction {
  /** View/read access to a resource */
  VIEW = 'view',
  /** Edit/write access to a resource */
  EDIT = 'edit',
  /** Export/download access to a resource */
  EXPORT = 'export',
}

/**
 * Valid permission paths in the system.
 *
 * These paths use dot-notation to represent the resource hierarchy.
 * Each path corresponds to a specific resource that can have permissions.
 *
 * @example
 * ```typescript
 * const path: PermissionPath = 'modules.headcount';
 * const canEdit = hasPermission(permissions, path, PermissionAction.EDIT);
 * ```
 */
export type PermissionPath =
  | 'backoffice.users'
  | 'modules.headcount'
  | 'modules.equipment';

/**
 * Permission set for a single resource.
 *
 * Each resource can have different permission levels (view, edit, export).
 * Not all resources support all actions - for example, modules typically
 * only support view and edit, while backoffice resources may support export.
 *
 * @interface ModulePermissions
 * @property {boolean} [view] - Whether the user can view/read this resource
 * @property {boolean} [edit] - Whether the user can edit/modify this resource
 * @property {boolean} [export] - Whether the user can export/download this resource
 *
 * @example
 * ```typescript
 * const headcountPerms: ModulePermissions = {
 *   view: true,
 *   edit: true,
 *   export: false
 * };
 * ```
 */
export interface ModulePermissions {
  /** View/read access */
  view?: boolean;
  /** Edit/write access */
  edit?: boolean;
  /** Export/download access */
  export?: boolean;
}

/**
 * Backoffice permissions structure.
 *
 * Represents all backoffice-related permissions in a nested structure.
 * This is the nested representation - the backend actually returns a flat
 * structure with dot-notation keys.
 *
 * @interface BackOfficePermissions
 * @property {ModulePermissions} [users] - Permissions for user management
 * @property {ModulePermissions} [logs] - Permissions for log viewing (future)
 *
 * @example
 * ```typescript
 * const backofficePerms: BackOfficePermissions = {
 *   users: { view: true, edit: true, export: true }
 * };
 * ```
 */
export interface BackOfficePermissions {
  /** User management permissions */
  users?: ModulePermissions;
  /** Log viewing permissions (reserved for future use) */
  logs?: ModulePermissions;
}

/**
 * Module permissions structure.
 *
 * Represents all module-related permissions in a nested structure.
 * Modules are the main application features (headcount, equipment, etc.).
 *
 * @interface ModulesPermissions
 * @property {ModulePermissions} [headcount] - Permissions for headcount module
 * @property {ModulePermissions} [equipment] - Permissions for equipment module
 *
 * @example
 * ```typescript
 * const modulePerms: ModulesPermissions = {
 *   headcount: { view: true, edit: true },
 *   equipment: { view: true, edit: false }
 * };
 * ```
 */
export interface ModulesPermissions {
  /** Headcount module permissions */
  headcount?: ModulePermissions;
  /** Equipment module permissions */
  equipment?: ModulePermissions;
}

/**
 * Complete user permissions structure (nested representation).
 *
 * This is a nested structure for easier access in TypeScript code.
 * The backend returns a flat structure, but this nested structure
 * can be used for type safety and easier property access.
 *
 * @interface UserPermissions
 * @property {BackOfficePermissions} [backoffice] - All backoffice permissions
 * @property {ModulesPermissions} [modules] - All module permissions
 * @property {any} [key: string] - Allow for future extensions
 *
 * @example
 * ```typescript
 * const userPerms: UserPermissions = {
 *   backoffice: {
 *     users: { view: true, edit: true, export: true }
 *   },
 *   modules: {
 *     headcount: { view: true, edit: true },
 *     equipment: { view: true, edit: true }
 *   }
 * };
 * ```
 */
export interface UserPermissions {
  /** Backoffice-related permissions */
  backoffice?: BackOfficePermissions;
  /** Module-related permissions */
  modules?: ModulesPermissions;
}

/**
 * Flat permissions structure as returned by the backend API.
 *
 * The backend uses dot-notation keys (e.g., "backoffice.users") to represent
 * the permission hierarchy. This matches exactly what the backend returns
 * from the `/auth/me` endpoint.
 *
 * This structure is what you'll receive from the API - use this type when
 * working directly with API responses.
 *
 * @interface FlatUserPermissions
 * @property {ModulePermissions} ['backoffice.users'] - User management permissions
 * @property {ModulePermissions} ['modules.headcount'] - Headcount module permissions
 * @property {ModulePermissions} ['modules.equipment'] - Equipment module permissions
 * @property {ModulePermissions | undefined} [key: string] - Allow for future extensions
 *
 * @example
 * ```typescript
 * // This is what the backend returns:
 * const apiResponse: FlatUserPermissions = {
 *   'backoffice.users': { view: true, edit: true, export: true },
 *   'modules.headcount': { view: true, edit: true },
 *   'modules.equipment': { view: true, edit: true }
 * };
 * ```
 *
 * @see {@link UserPermissions} For nested structure representation
 */
export interface FlatUserPermissions {
  'backoffice.users'?: ModulePermissions;
  'modules.headcount'?: ModulePermissions;
  'modules.equipment'?: ModulePermissions;
  [key: string]: ModulePermissions | undefined;
}
