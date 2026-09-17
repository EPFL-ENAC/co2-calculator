/**
 * Resolves how many rows a module table shows per page and which choices the
 * rows-per-page selector offers (#2681).
 *
 * Both come from the module config. A locked page size yields a single option:
 * QTable hides its rows-per-page selector when only one choice is offered, so
 * the user cannot change it. Kept free of Vue/i18n imports so it stays usable
 * from unit specs.
 */

import {
  DEFAULT_TABLE_PAGE_SIZE,
  TABLE_PAGE_SIZE_OPTIONS,
  type ModuleConfig,
  type TablePageSize,
} from '@/constant/moduleConfig';

export interface ResolvedTablePageSize {
  /** Initial rows per page for every table in the module. */
  rowsPerPage: TablePageSize;
  /** Choices for QTable's `rows-per-page-options`; one entry hides the selector. */
  rowsPerPageOptions: readonly TablePageSize[];
}

export function resolveTablePageSize(
  moduleConfig: Pick<ModuleConfig, 'tablePageSize' | 'tablePageSizeLocked'>,
): ResolvedTablePageSize {
  const rowsPerPage = moduleConfig.tablePageSize ?? DEFAULT_TABLE_PAGE_SIZE;
  return {
    rowsPerPage,
    rowsPerPageOptions: moduleConfig.tablePageSizeLocked
      ? [rowsPerPage]
      : TABLE_PAGE_SIZE_OPTIONS,
  };
}
