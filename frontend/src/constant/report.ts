// export type ReportType = 'usage' | 'results' | 'combined';
import type { ReportType } from 'src/api/backoffice';
import {
  outlinedBarChart,
  outlinedAssignment,
  outlinedPieChart,
  outlinedAddBox,
} from '@quasar/extras/material-icons-outlined';

export const REPORT_TYPES = [
  {
    value: 'results' as ReportType,
    icon: outlinedBarChart,
    titleKey: 'backoffice_reporting_generate_results_title',
    descriptionKey: 'backoffice_reporting_generate_results_description',
  },
  {
    value: 'detailed' as ReportType,
    icon: outlinedAssignment,
    titleKey: 'backoffice_reporting_generate_detailed_title',
    descriptionKey: 'backoffice_reporting_generate_detailed_description',
  },
  {
    value: 'usage' as ReportType,
    icon: outlinedPieChart,
    titleKey: 'backoffice_reporting_generate_usage_title',
    descriptionKey: 'backoffice_reporting_generate_usage_description',
  },
  {
    value: 'combined' as ReportType,
    icon: outlinedAddBox,
    titleKey: 'backoffice_reporting_generate_combined_title',
    descriptionKey: 'backoffice_reporting_generate_combined_description',
  },
];
