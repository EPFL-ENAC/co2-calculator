import { api } from 'src/api/http';

// ── Types ───────────────────────────────────────────────────────────

export type AuditAction =
  | 'CREATE'
  | 'READ'
  | 'UPDATE'
  | 'DELETE'
  | 'ROLLBACK'
  | 'TRANSFER';

export interface AuditLogEntry {
  id: number;
  entity_type: string;
  entity_id: number;
  version: number;
  change_type: AuditAction;
  change_reason: string | null;
  changed_by: number | null;
  changed_by_display_name?: string | null;
  changed_at: string;
  handler_id: string;
  handled_ids: string[];
  ip_address: string;
  route_path: string | null;
  message_summary: string | null;
}

export interface AuditLogDetail extends AuditLogEntry {
  data_snapshot: Record<string, unknown>;
  data_diff: {
    added: Record<string, unknown>;
    removed: Record<string, unknown>;
    changed: Record<string, { old: unknown; new: unknown }>;
  } | null;
}

export interface AuditStats {
  total_entries: number;
  creates: number;
  reads: number;
  updates: number;
  deletes: number;
}

export interface PaginationMeta {
  page: number;
  page_size: number;
  total: number;
}

export interface AuditLogListResponse {
  data: AuditLogEntry[];
  pagination: PaginationMeta;
}

export interface AuditQueryParams {
  user_id?: string;
  handler_id?: string;
  entity_type?: string;
  entity_id?: number;
  action?: AuditAction;
  date_from?: string;
  date_to?: string;
  search?: string;
  module?: string;
  page: number;
  page_size: number;
  sort_by: string;
  sort_desc: boolean;
}

// ── API functions ───────────────────────────────────────────────────

function toSearchParams(
  params: AuditQueryParams,
): Record<string, string | number | boolean> {
  const result: Record<string, string | number | boolean> = {};
  if (params.user_id) result.user_id = params.user_id;
  if (params.handler_id) result.handler_id = params.handler_id;
  if (params.entity_type) result.entity_type = params.entity_type;
  if (params.entity_id !== undefined) result.entity_id = params.entity_id;
  if (params.action) result.action = params.action;
  if (params.date_from) result.date_from = params.date_from;
  if (params.date_to) result.date_to = params.date_to;
  if (params.search) result.search = params.search;
  if (params.module) result.module = params.module;
  result.page = params.page;
  result.page_size = params.page_size;
  result.sort_by = params.sort_by;
  result.sort_desc = params.sort_desc;
  return result;
}

export async function fetchAuditLogs(
  params: AuditQueryParams,
): Promise<AuditLogListResponse> {
  return api
    .get('audit/activity', { searchParams: toSearchParams(params) })
    .json<AuditLogListResponse>();
}

export async function fetchAuditStats(
  params: AuditQueryParams,
): Promise<AuditStats> {
  return api
    .get('audit/stats', { searchParams: toSearchParams(params) })
    .json<AuditStats>();
}

export async function fetchAuditLogDetail(id: number): Promise<AuditLogDetail> {
  return api.get(`audit/activity/${id}`).json<AuditLogDetail>();
}

export async function exportAuditLogs(
  params: AuditQueryParams,
  format: 'csv' | 'json',
): Promise<Blob> {
  return api
    .get('audit/export', {
      searchParams: { ...toSearchParams(params), format },
    })
    .blob();
}
