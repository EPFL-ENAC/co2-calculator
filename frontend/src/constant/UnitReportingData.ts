export interface UnitReportingData {
  id: string | number;
  unit_name: string;
  affiliation: string;
  validation_status: string;
  principal_user: string;
  last_update: string;
  highest_result_category: string;
  total_carbon_footprint: number;
  year: number;
  total_fte?: number;
  view_url?: string;
  completion?: number;
  completion_progress?: string;
}
