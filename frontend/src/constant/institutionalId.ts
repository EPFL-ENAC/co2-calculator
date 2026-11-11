import { runtimeConfig } from '@/config/runtime';

/**
 * Label of the personal identifier the institution gives its members, stored
 * in headcount ("SCIPER" at EPFL). Set APP_INSTITUTION_ID_LABEL to change it.
 *
 * Used in headcount form labels, table column headers and error messages.
 */
export const INSTITUTIONAL_ID_LABEL = runtimeConfig.institution.idLabel;
