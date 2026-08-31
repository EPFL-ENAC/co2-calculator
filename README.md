# CO₂ Calculator

The CO₂ Calculator allows to assess the carbon footprint of a unit, in accordance with the Greenhouse Gas Protocol ([GHG Protocol](https://ghgprotocol.org/corporate-standard)), the international standard for calculating greenhouse gas emissions. Originally developed as a tool for EPFL, the calculator is an open-source project intended for broad adoption. It enables users to assess their environmental impact by entering relevant data across multiple sections.

**Project Status:** Under active development (v0.x.x internal/non-public releases)

**Access the platform:** See [Environments](docs/src/architecture/05-environments.md)
for the dev / stage / pre-production URLs and deployment topology.

> **Note:** Pre-production serves internal releases (v0.x.x) until the final
> v1.0.0 public release. The production environment activates with v1.0.0.

## 🚀 Quick Start

### Prerequisites

- **Make** (build automation)
- **Node.js** v24+ with npm
- **Python** 3.14+ with **uv** (install: `brew install uv`)
- **Docker** (for database)

### 1. Install dependencies

```bash
# Install all dependencies, set up git hooks, and create the
# env files below from their .example templates if missing
make install
# List helpful targets
make help
```

### 2. Configure environment files

The repo contains several `.env.example` files. For local development only one
needs editing:

| File                  | Created by `make install`         | What to do                                                                                            |
| --------------------- | --------------------------------- | ----------------------------------------------------------------------------------------------------- |
| `backend/.env`        | ✅ (from `backend/.env.example`)  | **Required:** uncomment the `localhost` `DB_URL` line (PostgreSQL — SQLite cannot run the migrations) |
| `.database.env`       | ✅ (from `.database.env.example`) | Nothing — credentials for the Dockerized PostgreSQL, already matching the `DB_URL` above              |
| `frontend/.env.local` | ❌ (copy `frontend/.env.example`) | Optional — only needed for Sentry/GlitchTip and other `APP_*` extras; the app runs fine without it    |

Keep the defaults from `backend/.env.example` — in particular `DEBUG=True`,
which enables the test login used below. No OAuth/OIDC or Accred credentials
are needed for local development.

### 3. Set up the database

```bash
# Start PostgreSQL (docker compose reads backend/.env and .database.env)
docker compose up -d postgres

# Create the database, run migrations, and seed development data
cd backend
make db-create
make db-migrate
make seed-data
```

### 4. Run the app

```bash
# Terminal 1 - Start backend (http://localhost:8000)
cd backend && make dev

# Terminal 2 - Start frontend (http://localhost:9000)
cd frontend && make dev
```

### 5. Log in

Open **<http://localhost:9000/en/login-test>** (or `/fr/login-test`) and pick a
test role.

- The language prefix is required — a bare `/login-test` is a 404.
- The default `/login` page goes through the real OAuth flow, which is not
  configured locally (it fails with `Missing "authorize_url"`).
- The test login page only exists when the backend runs with `DEBUG=True` and
  is never available in production builds.

### CI Validation (before pushing to dev/stage/main)

```bash
# Run all CI checks locally
make ci

# Or run individual checks
make lint          # Run linters
make type-check    # Type checking
make test          # Run tests
make build         # Build projects
```

> **Note:** Root Makefile provides CI validation commands. For development, use subfolder Makefiles directly (`cd backend && make dev`, `cd frontend && make dev`).

## 📊 Project Information

### Code Quality

[![Codecov](https://codecov.io/gh/EPFL-ENAC/co2-calculator/branch/main/graph/badge.svg?flag=backend)](https://codecov.io/gh/EPFL-ENAC/co2-calculator)

### Security & Status

[![Security](https://img.shields.io/github/actions/workflow/status/EPFL-ENAC/co2-calculator/security.yml?branch=main&label=security&logo=github&style=flat-square)](https://github.com/EPFL-ENAC/co2-calculator/actions/workflows/security.yml)
[![Dependency Review](https://img.shields.io/github/actions/workflow/status/EPFL-ENAC/co2-calculator/security.yml?branch=main&label=dependency%20review&logo=dependabot&style=flat-square)](https://github.com/EPFL-ENAC/co2-calculator/actions/workflows/security.yml)
[![NPM Audit](https://img.shields.io/github/actions/workflow/status/EPFL-ENAC/co2-calculator/security.yml?branch=main&label=npm%20audit&logo=npm&style=flat-square)](https://github.com/EPFL-ENAC/co2-calculator/actions/workflows/security.yml)
[![Python Security](https://img.shields.io/github/actions/workflow/status/EPFL-ENAC/co2-calculator/security.yml?branch=main&label=python%20security&logo=python&style=flat-square)](https://github.com/EPFL-ENAC/co2-calculator/actions/workflows/security.yml)
[![CodeQL](https://img.shields.io/github/actions/workflow/status/EPFL-ENAC/co2-calculator/security.yml?branch=main&label=CodeQL&logo=github&style=flat-square)](https://github.com/EPFL-ENAC/co2-calculator/security/code-scanning)
[![Secrets Scan](https://img.shields.io/github/actions/workflow/status/EPFL-ENAC/co2-calculator/security.yml?branch=main&label=secrets%20scan&logo=keycdn&style=flat-square)](https://github.com/EPFL-ENAC/co2-calculator/actions/workflows/security.yml)

### Contributors

- EPFL - (Research & Data): guilbep
- EPFL - ENAC-IT4R (Implementation): guilbep, BenBotros
- EPFL - ENAC-IT4R (Project Management): charlottegiseleweil, ambroise-dly
- EPFL - ENAC-IT4R (Contributors): ambroise-dly, domq, ymarcon, charlottegiseleweil

### Tech Stack

See [TECH STACK](./docs/src/architecture/08-tech-stack.md) for detailed technical specifications.

## Localization (i18n)

The application supports multiple languages through internationalization (i18n) files located in the frontend.

### Translation Files

Translation strings are stored as TypeScript objects in:

- **English (US):** `frontend/src/i18n/en-US/index.ts`
- **French (CH):** `frontend/src/i18n/fr-CH/index.ts`

### Modifying Translations

To add or update translation strings:

1. **Add/update keys in both locale files** - Ensure translation keys are identical across all locales:

```typescript
// frontend/src/i18n/en-US/index.ts
export default {
  my_new_key: "My English text",
  // ...
};

// frontend/src/i18n/fr-CH/index.ts
export default {
  my_new_key: "Mon texte en français",
  // ...
};
```

2. **Use descriptive key names** - Follow the pattern `component_element_purpose` (e.g., `login_button_submit`)
3. **Never remove keys still in use** - Check component usage before removing any translation key
4. **Test locally** - Run `cd frontend && make dev` to verify translations display correctly

### Contributing Translations

All translation changes must be submitted via GitHub pull request:

1. Create a feature branch from `dev`
2. Make your changes to the translation files
3. Commit with a conventional commit message (e.g., `feat(i18n): add dashboard translations`)
4. Push your branch and open a pull request
5. Ensure CI checks pass (run `make ci` locally first)

See [CONTRIBUTING.md](CONTRIBUTING.md) for detailed contribution guidelines and code of conduct.

## Contributing

Please read [CONTRIBUTING.md](CONTRIBUTING.md) for details on our code of conduct and the process for submitting pull requests.

## Status

Under active development. [Report bugs here](https://github.com/EPFL-ENAC/co2-calculator/issues).

## License

This project is licensed under the [GNU General Public License v3.0](LICENSE) - see the LICENSE file for details.

This is free software: you can redistribute it and/or modify it under the terms of the GPL-3.0 as published by the Free Software Foundation.
