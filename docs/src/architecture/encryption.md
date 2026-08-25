# Encryption and Key Management

Answers the two contractual security requirements ENAC-IT raises about
this service: how data processed by the service is encrypted in
transfer, and what measures protect the encryption keys. Read this
before answering a security questionnaire, and update it in the same PR
as any change to an encryption path.

**Reading time**: ~7 minutes

## TL;DR

| Contractual requirement                             | Status                                                                                                                                                 |
| --------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Specify and implement encryption for data transfer  | ⚠️ Active on every external hop, TLS 1.3 throughout; **not pinned** on the DB connection, and intra-cluster traffic is segmented rather than encrypted |
| Document and implement measures protecting the keys | ✅ Keys live in ENAC-IT's Infisical vault, injected at runtime, never in the repo — but no rotation runbook exists                                     |

Read the [Known gaps](#known-gaps) section before quoting either row.

## Scope: what these requirements do not ask for

Neither line asks for application-level encryption of business data at
rest in PostgreSQL. Use these arguments when the question comes back.

1. **The first requirement says "transfer".** At-rest protection is a
   different control, written differently wherever it is actually
   required. Answer the requirement as written.
2. **The second requirement is conditional on keys existing.** It
   obliges us to protect the keys we use; it does not oblige us to
   create more of them. ADR-014 §7 already phrases it "(if
   applicable)".
3. **At-rest has an owner, and it is not this codebase.** The database
   is EPFL DSI DBaaS. Ask DSI to attest storage-level and backup
   encryption. A control the platform attests beats the same control
   reimplemented one layer up.
4. **Column encryption would break the product.** Every published
   number is a SQL aggregation — the backend is the single source of
   truth. Encrypted columns cannot be indexed, filtered, joined, or
   summed, so aggregation would move into Python over full tables. The
   < 80 ms endpoint budget goes with it.
5. **It moves the risk rather than removing it.** The application needs
   the key to do its job and is the internet-facing component. Anyone
   who compromises the app gets plaintext. Column encryption only
   defends the raw-file and backup threat — exactly what storage-level
   encryption already covers.
6. **It would weaken compliance with the second requirement.** That
   requirement demands the _availability_ of keys. Encrypting the main
   dataset means one key incident destroys the emission data, this
   project's worst failure mode.

Offer instead: enforce `sslmode` on the database connection (below),
obtain DSI's attestation, and keep application-level encryption where
it is proportionate — connector secrets and uploaded files, both
already done.

> **⚠️ Do not claim the service processes no personal data.** Headcount
> rows ingested from Tableau persist a member name, institutional ID,
> and FTE. The proportionate control there is data minimisation and
> retention, not column encryption — but the claim itself is false and
> discredits any submission that carries it.

## Data in transfer

| Hop                           | Protection                         | Configured in                                           | Enforced   |
| ----------------------------- | ---------------------------------- | ------------------------------------------------------- | ---------- |
| Browser → ingress             | TLS, cert-manager + Let's Encrypt  | [Infra overview](../infra/01-overview.md#tlsssl)        | Yes        |
| App → object storage (S3)     | HTTPS                              | `S3_ENDPOINT_PROTOCOL`, defaults to `https`             | Yes        |
| App → PostgreSQL              | TLS 1.3, `TLS_AES_256_GCM_SHA384`  | `DB_URL` query string                                   | Not pinned |
| App → external APIs (Tableau) | HTTPS, certificate verification on | `TABLEAU_VERIFY_SSL`, `CONNECTOR_ALLOWED_HOST_SUFFIXES` | Yes        |
| Pod → pod inside the cluster  | None — segmented, not encrypted    | `helm/templates/network-policies.yaml`                  | n/a        |

Every database this service connects to negotiates TLS 1.3 with
`TLS_AES_256_GCM_SHA384` today. Verified on 2026-08-24 against each
environment:

```sql
select ssl, version, cipher from pg_stat_ssl where pid = pg_backend_pid();
--  ssl | version |         cipher
--  t   | TLSv1.3 | TLS_AES_256_GCM_SHA384
```

> **⚠️ Negotiated is not enforced.** `DB_URL` carries no `sslmode`, so
> libpq applies its default of `prefer`: it asks for TLS and accepts a
> plaintext connection without error if the server ever stops offering
> it. Pin it with `?sslmode=require` — the servers already support it,
> so this cannot break a connection. `sslmode=enable` is not a valid
> libpq value and fails at connect time.

`require` encrypts but does not authenticate the server. Move to
`verify-full` with an `sslrootcert` once EPFL DBaaS publishes a CA.

The runtime driver is psycopg 3 (`app/db.py` rewrites the URL to
`postgresql+psycopg`), so libpq rules apply and `sslmode` passes
through from `DB_URL`.

### Why intra-cluster traffic is not encrypted

Pod-to-pod traffic is confined rather than encrypted, which is the
proportionate control for this deployment:

- The cluster sits inside the EPFL network; nothing reaches a pod
  except through the load balancer and the ingress route.
- A `default-deny` NetworkPolicy denies all pod ingress, and named
  policies open only the routes actually needed — backend, frontend,
  and the OTel collector (`helm/templates/network-policies.yaml`, plus
  per-environment `network/` overlays in the ops repository).
- The trust boundary is therefore the namespace, enforced by policy,
  not by transport encryption.

A service mesh with mTLS would encrypt this hop. It is not deployed,
and adding one is an infrastructure decision, not an application one.

## Data at rest

### Uploaded files

CSV uploads are encrypted **by the application, before they reach
object storage**. `make_files_store` (`app/api/v1/files.py`) derives a
32-byte key with Scrypt (n=2¹⁴, r=8, p=1) from `FILES_ENCRYPTION_KEY`
and `FILES_ENCRYPTION_SALT`, then hands it to the `enacit4r-files`
store, which encrypts each file body with Fernet (AES-128-CBC +
HMAC-SHA256) before `put_object` and decrypts on read.

Server-side (bucket) encryption is a separate layer. This codebase
never requests it per object — no `ServerSideEncryption` parameter is
sent — but the buckets are **provisioned with encryption enabled**
through the EPFL XaaS portal, recorded in the Disaster Recovery Plan in
the private ops repository. So uploads are encrypted twice: once by the
application, once by the storage platform. See
[ADR-013](../architecture-decision-records/013-object-storage-strategy.md).

Those buckets are provisioned with **versioning disabled**, so a
deleted or overwritten object cannot be rolled back. That is a
durability limit, not an encryption one, but it belongs in the same
conversation with an auditor.

### Connection secrets

Credentials for API connectors (Tableau and future datasources) are
encrypted before they are written to the database.
`app/core/crypto.py` derives a Fernet key with the same Scrypt
parameters from the dedicated `CREDENTIALS_ENCRYPTION_KEY` and
`CREDENTIALS_ENCRYPTION_SALT` pair. See
[the 1552 plan](../implementation-plans/1552-api-connect-tableau-credentials-plan.md).

### Database

Hosted by EPFL DSI (DBaaS). Storage-level encryption is the provider's
responsibility; the application adds no column-level encryption beyond
the connection secrets above, deliberately — see
[Scope](#scope-what-these-requirements-do-not-ask-for).

Headcount entries ingested from Tableau hold personal data (member
name, institutional ID, FTE) in `DataEntry.data`. The ingestion path
already logs row counts only, never row contents.

## Encryption keys

### Inventory

Every key is a separate variable — none is reused across purposes
(audited in [#1704](../implementation-plans/1704-rename-secret-key-jwt-hmac-key.md)).

| Key                                              | Protects                      | Blast radius if rotated                         |
| ------------------------------------------------ | ----------------------------- | ----------------------------------------------- |
| `FILES_ENCRYPTION_KEY` + `FILES_ENCRYPTION_SALT` | Uploaded file bodies in S3    | **Every existing object becomes undecryptable** |
| `CREDENTIALS_ENCRYPTION_KEY` + `_SALT`           | Stored connector credentials  | **Every stored connector secret is orphaned**   |
| `JWT_HMAC_KEY`                                   | Access and refresh JWTs       | All sessions invalidated                        |
| `SESSION_HMAC_KEY`                               | 60-second mid-OAuth cookie    | In-flight logins fail, retry works              |
| `S3_SECRET_ACCESS_KEY`                           | Object storage authentication | Storage unreachable until updated               |

### Where keys live

Keys are stored in ENAC-IT's self-hosted Infisical vault, scoped per
environment, and reach the pod through the Infisical Kubernetes
operator:

```text
Infisical (per-env scope)
  → InfisicalSecret CRD, machine identity auth, 120 s resync
  → managed Kubernetes Secret in the app namespace
  → secretKeyRef env vars (helm/templates/_helpers.tpl)
  → Settings (app/core/config.py) → Scrypt → Fernet
```

The CRD lives in the ops repository, not here. `backend/.env.example`
ships every key **empty**, and the Helm chart references only key
_names_ — no key value exists anywhere in this repository or in a
container image.

Outside a local environment the application **refuses to boot** when
any of these keys is empty (`assert_security_settings` in
`app/main.py`). A missing key is a crash, never a silent downgrade to
plaintext.

### Availability, confidentiality, integrity

- **Confidentiality** — vault access is limited to authorized ENAC-IT
  personnel; keys are injected as environment variables at runtime and
  never written to code, config files, or images.
- **Availability** — the operator resyncs every 120 seconds and owns
  the managed Secret, so pods keep their keys across restarts. The
  vault is the single source: losing a file-encryption key means losing
  the ability to read every object encrypted with it.
- **Integrity** — key changes go through the vault, which is the only
  writer of the managed Secret. Vault-side audit and versioning are
  ENAC-IT's, documented in the private
  [security documentation repository](https://github.com/EPFL-ENAC/co2-calculator-security-doc).

## Known gaps

Stated openly, per the no-silent-fallbacks invariant in
[Engineering Guardrails](../contributing/guardrails.md).

| Gap                                                          | Impact                                                     |
| ------------------------------------------------------------ | ---------------------------------------------------------- |
| `DB_URL` carries no `sslmode`; libpq defaults to `prefer`    | TLS is live today, but nothing stops a silent downgrade    |
| No re-encryption runbook for `FILES_ENCRYPTION_KEY` rotation | The key cannot be rotated without losing stored files      |
| Intra-cluster pod-to-pod traffic is unencrypted              | Trust boundary is the namespace, enforced by NetworkPolicy |

## Next

Add `?sslmode=require` to the `DB_URL` secret in each environment —
verified safe, since every server already negotiates TLS 1.3 — then
close the first row of that table. Everything else needs an issue before
it needs a fix.
