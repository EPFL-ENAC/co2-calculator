import { defineStore } from 'pinia';
import { api } from '@/api/http';

/**
 * Hand-typed DTOs mirroring backend/app/schemas/connector.py (#1552).
 *
 * `make gen-api-types` normally regenerates `src/types/api/openapi.d.ts`
 * from the live backend's OpenAPI schema, but the only reachable local
 * backend during this change is an already-running debug session
 * (attached debugger, port 8000) started before the /connectors routes
 * existed — restarting it to pick up the new routes would kill that
 * session, and the committed `scripts/openapi.snapshot.json` fallback
 * also predates them. Hand-typed here instead; re-run
 * `cd frontend && make gen-api-types` against an up-to-date backend to
 * replace these with generated `paths['/connectors/...']` types.
 */
export interface ConnectorSpecRead {
  connector: string;
  label: string;
  form_fields: string[];
}

export interface ConnectorConnectionRead {
  id: number;
  connector: string;
  label: string;
  server_url: string;
  site_content_url: string | null;
  username: string;
  client_id: string;
  secret_id: string;
  has_secret: boolean;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface ConnectorConnectionPayload {
  label: string;
  server_url: string;
  site_content_url?: string;
  username: string;
  client_id: string;
  secret_id: string;
  // Omit/blank on an existing connection keeps the stored secret;
  // required by the backend when creating a new connection.
  secret_value?: string;
}

export interface ConnectorDatasourceRead {
  id: number;
  connection_id: number;
  module_type_id: number;
  data_entry_type_id: number | null;
  connector_luid: string;
  label: string;
  is_active: boolean;
}

export interface ConnectorDatasourcePayload {
  module_type_id: number;
  data_entry_type_id?: number;
  connector_luid: string;
  label: string;
}

export interface ConnectorTestResult {
  ok: boolean;
  detail: string;
}

export const useConnectorsStore = defineStore('connectors', () => {
  async function listConnectors(): Promise<ConnectorSpecRead[]> {
    return (await api.get('connectors').json()) as ConnectorSpecRead[];
  }

  async function getConnection(
    connector: string,
  ): Promise<ConnectorConnectionRead | null> {
    return (await api
      .get(`connectors/${connector}/connection`)
      .json()) as ConnectorConnectionRead | null;
  }

  async function saveConnection(
    connector: string,
    payload: ConnectorConnectionPayload,
  ): Promise<ConnectorConnectionRead> {
    return (await api
      .put(`connectors/${connector}/connection`, { json: payload })
      .json()) as ConnectorConnectionRead;
  }

  async function saveDatasource(
    connector: string,
    payload: ConnectorDatasourcePayload,
  ): Promise<ConnectorDatasourceRead> {
    return (await api
      .post(`connectors/${connector}/datasources`, { json: payload })
      .json()) as ConnectorDatasourceRead;
  }

  async function testConnection(
    connector: string,
  ): Promise<ConnectorTestResult> {
    return (await api
      .post(`connectors/${connector}/test`)
      .json()) as ConnectorTestResult;
  }

  return {
    listConnectors,
    getConnection,
    saveConnection,
    saveDatasource,
    testConnection,
  };
});
