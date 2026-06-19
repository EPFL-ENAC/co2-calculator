---
status: proposed
last_updated: 2026-06-19
title: "API Connect: connectors, connections and per-module datasources"
summary: "Make the backoffice 'API connect' form functional via a modular connector registry. Store one connection per connector (server/site/username + connected-app credentials entered in the form, secret encrypted at rest), bind a datasource LUID per module, and drive the travel + new headcount providers from one shared base provider."
---

# API Connect: connectors, connections and per-module datasources

The backoffice data-management dialog has an "API connect" form whose inputs
are bound to refs that are never sent to the backend — the submit path posts
an empty `config: {}`. Tableau settings live only in environment variables
and are hard-coded into `ProfessionalTravelApiProvider.__init__`. The form
does nothing, the connection cannot be reconfigured without a redeploy, and a
second datasource (headcount) cannot be added without copy-pasting the whole
provider.

This PRD introduces a **connector** abstraction: a hardcoded, modular
registry of integration types (today only `EPFL_TABLEAU`). Each connector has
one **connection** (where + who + credentials, entered in the form) and one
**datasource** per module (a LUID). The connected-app secret is encrypted at
rest.

## Goals

1. Store the connection in a new table — all fields entered in the form; the
   connected-app `secret_value` encrypted at rest.
2. Add an API for the dialog: list connectors, read/update a connection,
   manage its per-module datasources, test the connection.
3. Drive `ProfessionalTravelApiProvider` from the stored connection +
   datasource instead of environment variables.
4. Add `HeadcountMembersApiProvider` — same plumbing, a different LUID and
   field schema.
5. Abstract the shared Tableau logic into one `BaseTableauApiProvider`, and
   keep connectors modular so a second one is a registry entry plus a
   provider subclass.

## Non-goals

- No multi-tenant or per-user credentials — one connection per connector.
- No data backfill. Pre-v1.x drops the DB between deploys; operators
  re-enter the connection via the form after each deploy.
- No new emission logic. Headcount keeps its existing factor path; this work
  only feeds rows in.

## Decisions

These were settled during design; the rest of the document assumes them.

| Topic             | Decision                                                                                                                                             |
| ----------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
| Connector model   | A **hardcoded, modular registry** of connectors. Today only `EPFL_TABLEAU`. Adding one = a registry entry + a provider subclass.                     |
| Connection scope  | **One connection per connector.** Holds where/who + the connected-app credentials.                                                                   |
| Form fields       | The form captures `server_url`, `site_content_url`, `username`, `client_id`, `secret_id`, `secret_value`.                                            |
| Secrets           | `secret_value` is **encrypted at rest** (Fernet). Read schemas never return it; the form field is write-only (blank on edit keeps the stored value). |
| Datasource (LUID) | **Stored in DB** as `connector_luid` on a per-module datasource row. The field schema and transform stay in code.                                    |
| Env-only knobs    | `VERIFY_SSL`, `REQUEST_TIMEOUT_SECONDS`, `REST_MIN_API_VERSION`, `MAX_FIELDS` stay in env — runtime knobs, not connection state.                     |
| Encryption key    | A **dedicated** `CREDENTIALS_ENCRYPTION_KEY` + `CREDENTIALS_ENCRYPTION_SALT`, Scrypt→Fernet (mirrors file encryption). Never reuse `SECRET_KEY`.     |

> **Where each `TABLEAU_*` value goes.** Form → connection:
> `SERVER_URL`, `SITE_CONTENT_URL`, `USERNAME`, `CONNECTED_APP_CLIENT_ID`,
> `CONNECTED_APP_SECRET_ID`, `CONNECTED_APP_SECRET_VALUE` (the last
> encrypted). Per-module datasource: the former `DS_FLIGHTS_LUID` becomes
> `connector_luid`. Stays in env: `VERIFY_SSL`, `REQUEST_TIMEOUT_SECONDS`,
> `REST_MIN_API_VERSION`, `MAX_FIELDS`.

## Meta-architecture

```
API connect
   │
   ├─ 1. Choose connector ............... epfl-tableau (only entry today)
   │        from the hardcoded connector registry
   │
   ├─ 2. Connection (one per connector)  — entered in the form
   │      server_url, site_content_url, username,
   │      client_id, secret_id, secret_value*   (*encrypted at rest)
   │      └─ "Test connection" signs a JWT and calls Tableau auth
   │
   └─ 3. Datasource (per module)
          module_type (plane_travel | headcount), connector_luid
          └─ schema/transform is fixed in code, selected by module_type
                   │
                   ▼
          POST /sync/dispatch (ingestion_method=api, module_type)
                   │
          ProviderFactory → provider class (by module_type)
                   │
          BaseTableauApiProvider._ensure_credentials()
            loads datasource (connector_luid) + connection (creds, decrypt);
            reads runtime knobs from settings
                   │
          fetch → transform (per-module) → load DataEntry rows
```

## Data model

A hardcoded connector registry, two new tables, one new enum.

`ConnectorType` (str enum) — `EPFL_TABLEAU`.

`CONNECTORS` registry (code) — maps each `ConnectorType` to a
`ConnectorSpec`: a label and the list of form fields it exposes. Modular: a
new connector is one more entry plus a provider subclass.

`connector_connections` — one row per connector:

- `connector` (`ConnectorType`, unique), `label`
- `server_url`, `site_content_url`, `username`
- `client_id`, `secret_id`, `secret_value_encrypted`
- `is_active`, timestamps

`connector_datasources` — one row per module target:

- `connection_id` → `connector_connections.id`
- `module_type_id`, `data_entry_type_id` (nullable)
- `connector_luid`, `label`, `is_active`, timestamps
- unique active datasource per `(module_type_id, data_entry_type_id)`

Runtime knobs (`verify_ssl`, `request_timeout_seconds`,
`rest_min_api_version`, `max_fields`) are **not** columns — the provider
reads them from settings.

## Provider hierarchy

`BaseTableauApiProvider(DataIngestionProvider)` owns the shared plumbing —
JWT generation, sign-in, VDS read-metadata / query, caption validation,
`validate_connection`, `fetch_data`, the unit→carbon-report-module resolver,
and `_ensure_credentials()` (loads datasource + connection from the DB,
decrypts the secret, reads knobs from settings). Subclasses declare
`CONNECTOR`, `MODULE_TYPE`, `DATA_ENTRY_TYPE`, `REQUIRED_CAPTIONS`, and
implement `transform_data` plus per-row `_build_data_entry`.

- `ProfessionalTravelApiProvider` — keeps the plane mapping and the
  `OUT_CO2_CORRECTED` override carrier.
- `HeadcountMembersApiProvider` — maps to `member` rows
  (`name`, `sius_code`, `user_institutional_id`, `fte`, unit).

## Security considerations

- **Encryption at rest (A04).** `secret_value` is Fernet-encrypted with a
  Scrypt-derived key; plaintext never touches the column or logs.
- **No secret echo.** Read schemas expose only `has_secret: bool`. The form's
  secret field is write-only and blank on edit; an empty value on update
  keeps the stored secret rather than clearing it.
- **Fail-closed (A10).** Encrypt/decrypt raise if the key/salt are unset; a
  connection cannot be saved or used without configured keys.
- **Deny by default (A01).** Connector, connection and datasource endpoints
  reuse the same backoffice permission gate as `/sync/dispatch`. No role
  checks in the UI — gate on permission keys.

## Rollout

- Add `CREDENTIALS_ENCRYPTION_KEY` / `CREDENTIALS_ENCRYPTION_SALT` to every
  environment before deploy; without them the API fails closed. The knob env
  vars (`TABLEAU_VERIFY_SSL`, …) stay.
- Add `cryptography` as a direct backend dependency (currently transitive
  via `enacit4r-files`) — supply-chain hygiene (A03).
- After deploy (the DB is dropped between pre-v1 deploys), an operator opens
  the dialog, picks the connector, enters the connection once, and sets the
  `connector_luid` per module. Travel imports that used env vars must be
  re-entered through the form — there is no automatic migration.

## Open questions

- Should `secret_id` also be encrypted? It is an identifier (`kid`), not a
  secret; left plaintext unless the security review says otherwise.

## Next action

Implement per the companion plan:
[1552-api-connect-tableau-credentials-plan.md](1552-api-connect-tableau-credentials-plan.md).
