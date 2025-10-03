# epfl-calculator-co2

200 - Calculator Co2 (enacit4r-project-200-st, enacit4r-project-200-dev)

**Access the platform here:**

**dev url: [https://epfl-calculator-co2-dev.epfl.ch/](https://epfl-calculator-co2-dev.epfl.ch/)**  
**prod url: [https://epfl-calculator-co2.epfl.ch/](https://epfl-calculator-co2.epfl.ch/)**

## Contributors

- EPFL - (Research & Data): guilbep
- EPFL - ENAC-IT4R (Implementation):
- EPFL - ENAC-IT4R (Project Management):
- EPFL - ENAC-IT4R (Contributors):

## Tech Stack

### Frontend

- [Vue.js 3](https://vuejs.org/) - Progressive JavaScript Framework
- [Quasar](https://quasar.dev/) - Vue.js Framework
- [OpenLayers](https://openlayers.org/) - Mapping Library
- [ECharts](https://echarts.apache.org/) - Data Visualization
- [nginx](https://nginx.org/) - Web Server

### Backend

- [Python](https://www.python.org/) with FastAPI
- [PostgreSQL](https://www.postgresql.org/) - Database

### Infrastructure

- [Docker](https://www.docker.com/) - Containerization
- [Traefik](https://traefik.io/) - Edge Router

_Note: Update this section with your actual tech stack_

## Development

### Prerequisites

- Node.js (v22+)
- npm
- Python 3
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

### Main Data Repository

- Location: enacit4r-project-200
- ## Contains:
  -

### Application Data

- Location: enacit4r-project-200 `./`
- Contains:
  - Application-specific data

Data is version-controlled and regularly updated to reflect the latest research findings

## Internationalization

The platform supports multiple languages including English, French, and Arabic. Translations are managed through i18n files located in `frontend/src/i18n/`. based on `frontend/src/assets/i18n`

## Contributing

Please read [CONTRIBUTING.md](CONTRIBUTING.md) for details on our code of conduct and the process for submitting pull requests.

## Status

Under active development. [Report bugs here](https://github.com/EPFL-ENAC/epfl-calculator-co2/issues).

## License

This project is licensed under the [GNU General Public License v3.0](LICENSE) - see the LICENSE file for details.

This is free software: you can redistribute it and/or modify it under the terms of the GPL-3.0 as published by the Free Software Foundation.

# Setup Checklist Completed

The following items from the original setup checklist have been automatically completed:

- [x] Replace `{ YOUR-REPO-NAME }` in all files by the name of your repo
- [x] Replace `{ YOUR-LAB-NAME }` in all files by the name of your lab
- [x] Replace `{ DESCRIPTION }` with project description
- [x] Replace assignees: githubusernameassignee by the github handle of your assignee
- [x] Handle CITATION.cff file (kept/removed based on preference)
- [x] Handle release-please workflow (kept/removed based on preference)
- [x] Configure project-specific settings

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
