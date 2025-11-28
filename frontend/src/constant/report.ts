export type ReportType = 'usage' | 'results' | 'combined';

export const REPORT_TYPES = [
  {
    value: 'usage' as ReportType,
    icon: 'o_pie_chart',
    titleKey: 'backoffice_reporting_generate_usage_title',
    descriptionKey: 'backoffice_reporting_generate_usage_description',
  },
  {
    value: 'results' as ReportType,
    icon: 'o_bar_chart',
    titleKey: 'backoffice_reporting_generate_results_title',
    descriptionKey: 'backoffice_reporting_generate_results_description',
  },
  {
    value: 'combined' as ReportType,
    icon: 'o_add_box',
    titleKey: 'backoffice_reporting_generate_combined_title',
    descriptionKey: 'backoffice_reporting_generate_combined_description',
  },
];
