---
status: proposed
last_updated: 2026-06-19
title: "API Connect: user-managed encrypted Tableau credentials"
summary: "Make the backoffice 'API connect' form functional: store one shared, encrypted EPFL-Tableau connection plus per-module datasource (LUID) bindings, drive the existing professional-travel provider and a new headcount-members provider from those records, and abstract the shared Tableau logic into one base provider."
---

# API Connect: user-managed encrypted Tableau credentials

The backoffice data-management dialog has an "API connect" form whose four
inputs (server URL, client ID, secret ID, secret value) are bound to refs
that are never sent to the backend — the submit path posts an empty
`config: {}`. Tableau credentials live only in environment variables and are
hard-coded into `ProfessionalTravelApiProvider.__init__`. As a result the
form does nothing, credentials cannot be rotated without a redeploy, and a
second Tableau datasource (headcount) cannot be added without copy-pasting
the whole provider.

This PRD defines a connection-and-binding model that makes the form real,
encrypts secrets at rest, and lets one shared Tableau connection feed many
modules — each pointing at its own datasource LUID.

## Goals

1. Persist Tableau credentials in a new table, with the connected-app secret
   encrypted at rest using a dedicated key.
2. Add an API for the dialog: create/update/test a connection and manage its
   per-module datasource bindings.
3. Drive `ProfessionalTravelApiProvider` from the stored connection +
   binding instead of environment variables.
4. Add `HeadcountMembersApiProvider` — same Tableau plumbing, a different
   LUID and field schema.
5. Abstract the shared Tableau logic into one `BaseTableauApiProvider` so the
   two providers stay DRY.

## Non-goals

- No multi-tenant or per-user credentials — one shared connection per
  provider type (see Decisions).
- No data backfill. Pre-v1.x drops the DB between deploys; operators
  re-enter the connection via the form after each deploy.
- No new emission logic. Headcount keeps its existing factor/emission path;
  this work only feeds rows in.

## Decisions

These three were settled during design; the rest of the document assumes
them.

| Topic            | Decision                                                                                                                                             |
| ---------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
| Credential model | **One shared connection** per provider type. The connected-app credentials are reused across modules; only the datasource LUID differs.              |
| LUID + schema    | **LUID stored in DB** on a per-module binding row. The field schema and transform stay in code (they are logic, not data).                           |
| Encryption key   | **New dedicated key** — `CREDENTIALS_ENCRYPTION_KEY` + `CREDENTIALS_ENCRYPTION_SALT`, Scrypt→Fernet, mirroring the existing file-encryption pattern. |

> **Reconciliation of the credential keys.** The connection config block is
> `TABLEAU_SERVER_URL`, `TABLEAU_SITE_CONTENT_URL`, `TABLEAU_USERNAME`,
> `TABLEAU_VERIFY_SSL`, `TABLEAU_REQUEST_TIMEOUT_SECONDS`,
> `TABLEAU_REST_MIN_API_VERSION`, `TABLEAU_MAX_FIELDS`, **plus** the
> connected-app auth trio the provider signs JWTs with
> (`TABLEAU_CONNECTED_APP_CLIENT_ID/SECRET_ID/SECRET_VALUE`, surfaced by the
> form's Client ID / Secret ID / Secret Value fields).
> `TABLEAU_DS_FLIGHTS_LUID` is **not** on the connection — it becomes a
> datasource binding. Only `secret_value` is encrypted; the rest are
> identifiers or operational knobs.

## Meta-architecture

The form walks two records: a shared connection, then the module's binding.

```
API connect
   │
   ├─ 1. Choose provider type ............ EPFL_TABLEAU (only value today)
   │
   ├─ 2. Connection (shared, encrypted)
   │      server_url, site_content_url, username,
   │      client_id, secret_id, secret_value*  (*encrypted at rest)
   │      verify_ssl, timeout, api_version, max_fields
   │      └─ reused by every module; "Test connection" signs a JWT
   │
   └─ 3. Datasource binding (per module)
          module_type (plane_travel | headcount), datasource_luid
          └─ schema/transform is fixed in code, selected by module_type
                   │
                   ▼
          POST /sync/dispatch (ingestion_method=api, module_type)
                   │
          ProviderFactory → provider class (by module_type)
                   │
          BaseTableauApiProvider._ensure_credentials()
            loads binding (LUID) + connection (creds, decrypts secret)
                   │
          fetch → transform (per-module) → load DataEntry rows
```

## Data model

Two new tables (SQLModel), one new enum.

`external_connections` — one row per provider type:

- `provider_type` (`ExternalProviderType`, unique), `label`
- `server_url`, `site_content_url`, `username`
- `client_id`, `secret_id`, `secret_value_encrypted`
- `verify_ssl`, `request_timeout_seconds`, `rest_min_api_version`,
  `max_fields`, `is_active`, timestamps

`external_datasource_bindings` — one row per module target:

- `connection_id` → `external_connections.id`
- `module_type_id`, `data_entry_type_id` (nullable)
- `datasource_luid`, `label`, `is_active`, timestamps
- unique active binding per `(module_type_id, data_entry_type_id)`

## Provider hierarchy

`BaseTableauApiProvider(DataIngestionProvider)` owns the shared plumbing —
JWT generation, sign-in, VDS read-metadata / query, caption validation,
`validate_connection`, `fetch_data`, the unit→carbon-report-module resolver,
and `_ensure_credentials()` (loads binding + connection from the DB and
decrypts the secret). Subclasses declare `MODULE_TYPE`, `DATA_ENTRY_TYPE`,
`REQUIRED_CAPTIONS`, and implement `transform_data` plus per-row
`_build_data_entry`.

- `ProfessionalTravelApiProvider` — keeps the plane mapping and the
  `OUT_CO2_CORRECTED` override carrier.
- `HeadcountMembersApiProvider` — maps to `member` rows
  (`name`, `sius_code`, `user_institutional_id`, `fte`, unit).

## Security considerations

- **Encryption at rest (A04).** `secret_value` is Fernet-encrypted with a
  Scrypt-derived key; plaintext never touches the column or logs.
- **Fail-closed (A10).** Encrypt/decrypt raise if the key/salt are unset; a
  connection cannot be saved or used without configured keys.
- **Deny by default (A01).** Connection and binding endpoints reuse the same
  backoffice permission gate as `/sync/dispatch`. No role checks in the UI —
  gate on permission keys.
- **No secret echo.** Read schemas never return `secret_value`; the API
  reports only whether a secret is set. The form's secret field is
  write-only and blank on edit.
- **No secrets in logs.** Existing Tableau logging already logs ids, not the
  secret value; the base provider preserves that.

## Rollout

- Add `CREDENTIALS_ENCRYPTION_KEY` / `CREDENTIALS_ENCRYPTION_SALT` to every
  environment before deploy; without them the API fails closed.
- Add `cryptography` as a direct backend dependency (currently transitive
  via `enacit4r-files`) — supply-chain hygiene (A03).
- After deploy, an operator opens the dialog, saves the connection once, and
  sets the LUID per module. Travel imports that used env vars must be
  re-pointed through the form — there is no automatic migration.

## Open questions

- Should `secret_id` also be encrypted? It is an identifier (`kid`), not a
  secret; left plaintext unless the security review says otherwise.
- Optional dev convenience: seed a connection from the existing `TABLEAU_*`
  env vars when the table is empty, gated to non-prod. Deferred — not
  required for the goal.

## Next action

Implement per the companion plan:
[1552-api-connect-tableau-credentials-plan.md](1552-api-connect-tableau-credentials-plan.md).
