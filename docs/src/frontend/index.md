# Frontend Overview

This section provides an overview of the frontend layer architecture, technologies, and integration points.

## Architecture Pattern

- **Framework**: Vue 3 Composition API
- **UI Library**: Quasar Framework
- **State Management**: Pinia
- **Routing**: Vue Router
- **HTTP Client**: Axios
- **Authentication**: oidc-client-ts

## Main Technologies

- Vue 3 for reactive UI components
- Quasar for responsive UI components and utilities
- Pinia for state management
- Vue Router for client-side routing
- oidc-client-ts for OpenID Connect authentication
- eCharts for data visualization

## API Interface

The frontend communicates with the backend through a RESTful API:

- Base URL: `/api/v1/`
- Authentication: Bearer token in Authorization header
- Content Type: JSON for requests and responses
- Error Handling: Standard HTTP status codes with JSON error bodies

## Integration Points

- **Authentication Service**: Microsoft Entra ID (OIDC)
- **Backend API**: FastAPI REST endpoints
- **Static Assets**: Served directly by web server

## Subsystems

- [Architecture](./architecture.md) - Detailed frontend architecture
- [UI System](./ui-system.md) - Component library and design system
- [API Integration](./api.md) - Data layer and API communication
- [Development Guide](./dev-guide.md) - Setup and development workflows
- [Testing](./testing.md) - Testing strategies and tools
- [Deployment](./deploy.md) - Build and deployment processes

For architectural overview, see [Architecture Overview](../architecture/index.md).
