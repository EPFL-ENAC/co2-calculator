# CO₂ Calculator

**Project Status:** Under active development (v0.x.x internal/non-public releases)

**Access the platform:**

- **dev:** [https://co2-calculator-dev.epfl.ch/](https://co2-calculator-dev.epfl.ch/)
- **stage:** [https://co2-calculator-stage.epfl.ch/](https://co2-calculator-stage.epfl.ch/)]
- **pre-production:** [https://co2-calculator.epfl.ch/](https://co2-calculator.epfl.ch/)

> **Note:** Pre-production serves internal releases (v0.x.x) until final v1.0.0 public release. Production environment will activate with v1.0.0.

## 🚀 Quick Start

### Prerequisites

- **Make** (build automation)
- **Node.js** v24+ with npm
- **Python** 3.12+ with **uv** (install: `brew install uv`)
- **Docker** (for database)

### Installation

```bash
# Install all dependencies and set up git hooks
make install
# List helpful targets
make help
```

### Development Workflow

**Option 1: Run services separately (recommended)**

```bash
# Terminal 1 - Start backend (http://localhost:8000)
cd backend && make dev

# Terminal 2 - Start frontend (http://localhost:9000)
cd frontend && make dev
```

**Option 2: Database management (if needed)**

```bash
# Start PostgreSQL
docker compose up -d postgres

# Run migrations
cd backend && make db-migrate
```

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

1. Create a feature branch from `main`
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
