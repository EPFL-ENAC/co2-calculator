---
status: delivered
issue: 1713
last_updated: 2026-07-07
title: "Backend provider configuration naming cleanup"
summary: "Split the overloaded PROVIDER_PLUGIN/ACCRED_API_URL env contract into explicit ROLE_PROVIDER_TYPE / UNIT_PROVIDER_TYPE / ACCRED_* config, renaming DefaultRoleProvider/DefaultUnitProvider and decoupling provider-selection enums from the persisted UserProvider metadata enum."
---

# Backend provider configuration naming cleanup

## Problem

`PROVIDER_PLUGIN` is one generic env var driving two unrelated backend
concerns: `RoleProvider` (source of app roles/authorizations) and
`UnitProvider` (source of institutional units). `default` doesn't mean the
same thing in both: `DefaultRoleProvider` = roles from JWT/OIDC claims;
`DefaultUnitProvider` = units from the local database — same string, opposite
semantics. `UserProvider` is also overloaded: used both for provider
_selection_ config and as persisted _source metadata_ on `User`/`Unit`
models. These are different concepts and must not share an enum.

Goal: backend config should separately and explicitly answer — where do
roles come from? where do units come from? how does the backend talk to
Accred? what provider/source metadata is persisted on users/units? No
`default` naming anywhere; invalid/missing config fails hard at startup, no
fallback.

Non-goal: frontend runtime config (frontend already has `injectEnv.js`); no
new `/runtime-config` endpoint.

## Design

### Env contract

Remove: `PROVIDER_PLUGIN`, `ACCRED_API_URL`.

Add:

- `ROLE_PROVIDER_TYPE` (`jwt|accred|test`)
- `UNIT_PROVIDER_TYPE` (`database|accred|test`)
- `ACCRED_API_BASE_URL`
- `ACCRED_API_USERNAME`
- `ACCRED_API_KEY`
- `ACCRED_AUTHORIZATION_HEALTHCHECK_URL`

### Naming rules

- `*_PROVIDER_TYPE` = backend implementation selection.
- `ACCRED_*` = backend machine-to-machine Accred integration config.
- Provider/source metadata on models = persisted origin of user/unit data.
- Do **not** rename `ACCRED_API_BASE_URL` to `ROLE_PROVIDER_API_URL` — Accred
  is used by both RoleProvider and UnitProvider, so the API URL belongs to
  the Accred integration, not to role resolution specifically.
- `UserProvider` is not reused for config selection. It may remain as
  persisted/source metadata (`User.provider = accred|test|oidc/jwt`,
  `Unit.provider = accred|database|test`), but selection config and
  persisted metadata must never be the same enum.

### Config types

```py
class RoleProviderType(str, Enum):
    JWT = "jwt"; ACCRED = "accred"; TEST = "test"

class UnitProviderType(str, Enum):
    DATABASE = "database"; ACCRED = "accred"; TEST = "test"
```

### Settings + validator

```py
class Settings(BaseSettings):
    ROLE_PROVIDER_TYPE: RoleProviderType
    UNIT_PROVIDER_TYPE: UnitProviderType
    ACCRED_API_BASE_URL: AnyHttpUrl | None = None
    ACCRED_API_USERNAME: str | None = None
    ACCRED_API_KEY: str | None = None
    ACCRED_AUTHORIZATION_HEALTHCHECK_URL: AnyHttpUrl | None = None

    @model_validator(mode="after")
    def validate_accred_config(self):
        uses_accred = (
            self.ROLE_PROVIDER_TYPE == RoleProviderType.ACCRED
            or self.UNIT_PROVIDER_TYPE == UnitProviderType.ACCRED
        )
        if uses_accred:
            missing = [
                n for n in ("ACCRED_API_BASE_URL", "ACCRED_API_USERNAME", "ACCRED_API_KEY")
                if getattr(self, n) is None
            ]
            if missing:
                raise ValueError("Missing required Accred config: " + ", ".join(missing))
        return self
```

No fallback, no compatibility layer, no deprecated env support — missing or
invalid config fails at startup.

### Factories

- `get_role_provider()` reads `settings.ROLE_PROVIDER_TYPE` (was
  `PROVIDER_PLUGIN`), match/case -> `JwtClaimsRoleProvider` (renamed from
  `DefaultRoleProvider`), `AccredRoleProvider`, `TestRoleProvider`.
- `get_unit_provider()` reads `settings.UNIT_PROVIDER_TYPE` (was
  `PROVIDER_PLUGIN`), match/case -> `DatabaseUnitProvider` (renamed from
  `DefaultUnitProvider`), `AccredUnitProvider`, `TestUnitProvider`.

### Accred providers

Both `AccredRoleProvider` and `AccredUnitProvider` switch to
`settings.ACCRED_API_BASE_URL` / `ACCRED_API_USERNAME` / `ACCRED_API_KEY`,
dropping `settings.ACCRED_API_URL`. Constructors assume already-validated
config — no constructor-level "credentials not fully configured" warnings;
invalid config is a startup `Settings` error, not a runtime provider
warning.

### Healthcheck

`ACCRED_AUTHORIZATION_HEALTHCHECK_URL` is specifically an
authorization-readiness check (backend credentials can reach Accred and
read expected authorization data) — not a generic API health URL.

### Breaking changes

`PROVIDER_PLUGIN` and `ACCRED_API_URL` are removed outright. No deprecated
fallback, no migration compatibility. Deployment manifests must be updated
in the same PR.

## Steps

- [ ] Add `RoleProviderType`/`UnitProviderType` enums and rewrite `Settings`
      (`ROLE_PROVIDER_TYPE`, `UNIT_PROVIDER_TYPE`, `ACCRED_API_BASE_URL`,
      `ACCRED_API_USERNAME`, `ACCRED_API_KEY`,
      `ACCRED_AUTHORIZATION_HEALTHCHECK_URL`) with the `validate_accred_config`
      model validator, in `backend/app/core/config.py`
- [ ] Rename `DefaultRoleProvider` -> `JwtClaimsRoleProvider`; rewire
      `get_role_provider()` to dispatch on `settings.ROLE_PROVIDER_TYPE` in
      `backend/app/providers/role_provider.py`
- [ ] Rename `DefaultUnitProvider` -> `DatabaseUnitProvider`; rewire
      `get_unit_provider()` to dispatch on `settings.UNIT_PROVIDER_TYPE` in
      `backend/app/providers/unit_provider.py`
- [ ] Update `AccredRoleProvider`/`AccredUnitProvider` to read
      `ACCRED_API_BASE_URL`/`ACCRED_API_USERNAME`/`ACCRED_API_KEY`; drop
      `ACCRED_API_URL` and the constructor-level config warning
- [ ] Update deployment manifests to the new env var names (remove
      `PROVIDER_PLUGIN`, `ACCRED_API_URL`; add `ROLE_PROVIDER_TYPE`,
      `UNIT_PROVIDER_TYPE`, `ACCRED_API_BASE_URL`, `ACCRED_API_USERNAME`,
      `ACCRED_API_KEY`, `ACCRED_AUTHORIZATION_HEALTHCHECK_URL`)
- [ ] Config tests: missing/invalid `ROLE_PROVIDER_TYPE`/`UNIT_PROVIDER_TYPE`
      fail startup; Accred selection requires the 3 `ACCRED_*` vars; jwt/database
      selection doesn't require them
- [ ] Factory tests: each provider type returns the right class for both
      `get_role_provider()` and `get_unit_provider()`
- [ ] Regression tests: factories no longer read `PROVIDER_PLUGIN`; Accred
      providers no longer read `ACCRED_API_URL`
- [ ] Update backend `.env.example` with the new vars and a short config note
