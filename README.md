# epfl-calculator-co2

- Security
  [![Security](https://img.shields.io/github/actions/workflow/status/EPFL-ENAC/co2-calculator/security.yml?branch=main&label=security&logo=github&style=flat-square)](https://github.com/EPFL-ENAC/co2-calculator/actions/workflows/security.yml)
  [![Dependency Review](https://img.shields.io/github/actions/workflow/status/EPFL-ENAC/co2-calculator/security.yml?branch=main&label=dependency%20review&logo=dependabot&style=flat-square)](https://github.com/EPFL-ENAC/co2-calculator/actions/workflows/security.yml)
  [![NPM Audit](https://img.shields.io/github/actions/workflow/status/EPFL-ENAC/co2-calculator/security.yml?branch=main&label=npm%20audit&logo=npm&style=flat-square)](https://github.com/EPFL-ENAC/co2-calculator/actions/workflows/security.yml)
  [![Python Security](https://img.shields.io/github/actions/workflow/status/EPFL-ENAC/co2-calculator/security.yml?branch=main&label=python%20security&logo=python&style=flat-square)](https://github.com/EPFL-ENAC/co2-calculator/actions/workflows/security.yml)
  [![CodeQL](https://img.shields.io/github/actions/workflow/status/EPFL-ENAC/co2-calculator/security.yml?branch=main&label=CodeQL&logo=github&style=flat-square)](https://github.com/EPFL-ENAC/co2-calculator/security/code-scanning)
  [![Secrets Scan](https://img.shields.io/github/actions/workflow/status/EPFL-ENAC/co2-calculator/security.yml?branch=main&label=secrets%20scan&logo=keycdn&style=flat-square)](https://github.com/EPFL-ENAC/co2-calculator/actions/workflows/security.yml)

-

200 - Calculator Co2 (enacit4r-project-200-st, enacit4r-project-200-dev)

**Project Status:** Under active development (v0.x.x internal/non-public releases)

**Access the platform here:**

**dev url: [https://epfl-calculator-co2-dev.epfl.ch/](https://epfl-calculator-co2-dev.epfl.ch/)**
**pre-production url: [https://epfl-calculator-co2.epfl.ch/](https://epfl-calculator-co2.epfl.ch/)**

**Note:** The pre-production url currently serves internal/non-public releases (v0.x.x) until the final v1.0.0 public release at the end of the 10-sprint development process.

**Note:** The production environment will be activated with the v1.0.0 public-facing release at the end of the 10-sprint development process. Current releases are internal/non-public versions (v0.x.x) released at the end of each sprint for internal testing.

## Contributors

- EPFL - (Research & Data): guilbep
- EPFL - ENAC-IT4R (Implementation):
- EPFL - ENAC-IT4R (Project Management):
- EPFL - ENAC-IT4R (Contributors):

## Tech Stack

- cf [TECH STACK](./TECH_SPEC.md)

## Development

### Prerequisites

- Make
- Node.js (v22+)
  - npm
- Python 3.13
  - uv
- Docker

### Setup & Usage

You can use Make with the following commands:

```bash
make install
make clean
make uninstall
make lint
make format
```

_Note: Update these commands based on your project's actual build system_

### Development Environment

The development environment includes:

- Frontend at http://localhost:9000
- Backend API at https://localhost:8060
- Traefik Dashboard at http://localhost:8080

## Data Management

Data for the platform is organized the following way:

- TBD

## Internationalization

The platform supports multiple languages including English, French. Translations are managed through i18n files located in `frontend/src/i18n/`. based on `frontend/src/assets/i18n`

## Contributing

Please read [CONTRIBUTING.md](CONTRIBUTING.md) for details on our code of conduct and the process for submitting pull requests.

## Status

Under active development. [Report bugs here](https://github.com/EPFL-ENAC/epfl-calculator-co2/issues).

## License

This project is licensed under the [GNU General Public License v3.0](LICENSE) - see the LICENSE file for details.

This is free software: you can redistribute it and/or modify it under the terms of the GPL-3.0 as published by the Free Software Foundation.

## Remaining Manual Tasks

Please complete these tasks manually:

- [ ] Add token for the github action secrets called: MY_RELEASE_PLEASE_TOKEN (since you kept the release-please workflow)
- [ ] Check if you need all the labels: https://github.com/EPFL-ENAC/epfl-calculator-co2/labels
- [ ] Create your first milestone: https://github.com/EPFL-ENAC/epfl-calculator-co2/milestones
- [ ] Protect your branch if you're a pro user: https://github.com/EPFL-ENAC/epfl-calculator-co2/settings/branches
- [ ] [Activate discussion](https://github.com/EPFL-ENAC/epfl-calculator-co2/settings)

## Helpful links

- [How to format citations ?](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-citation-files)
- [Learn how to use github template repository](https://docs.github.com/en/repositories/creating-and-managing-repositories/creating-a-repository-from-a-template)
