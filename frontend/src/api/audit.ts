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
  sync_status: string | null;
  sync_error: string | null;
  synced_at: string | null;
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
  return { ...params };
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
