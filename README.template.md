# { YOUR-REPO-NAME }

{ DESCRIPTION }

**Access the platform here:**

**dev url: [https://{ YOUR-REPO-NAME }-dev.epfl.ch/](https://{ YOUR-REPO-NAME }-dev.epfl.ch/)**  
**prod url: [https://{ YOUR-REPO-NAME }.epfl.ch/](https://{ YOUR-REPO-NAME }.epfl.ch/)**

## Contributors

- EPFL - (Research & Data): [Add main researchers]
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

- Location:
- ## Contains:
  -

### Application Data

- Location: `./`
- Contains:
  - Application-specific data
  - Configuration files
  - Smaller datasets ..

Data is version-controlled and regularly updated to reflect the latest research findings

## Internationalization

The platform supports multiple languages including English, French, and Arabic. Translations are managed through i18n files located in `frontend/src/i18n/`. based on `frontend/src/assets/i18n`

## Contributing

Please read [CONTRIBUTING.md](CONTRIBUTING.md) for details on our code of conduct and the process for submitting pull requests.

## Status

Under active development. [Report bugs here](https://github.com/EPFL-ENAC/{ YOUR-REPO-NAME }/issues).

## License

This project is licensed under the [GNU General Public License v3.0](LICENSE) - see the LICENSE file for details.

This is free software: you can redistribute it and/or modify it under the terms of the GPL-3.0 as published by the Free Software Foundation.
