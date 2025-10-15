# Tech Stack Rationale

The technology stack was chosen based on team expertise, project requirements, and long-term maintainability considerations.

## Why mkdocs for the documentation

Selected for:

- Possible to use with CMS
- Markdown compatible with github
- Easy to add i18n + mermaid

## Why Vue.js for Frontend?

Selected for:

- Reactive data binding and component-based architecture
- Rich ecosystem and community support
- Good performance with Quasar UI framework
- Team familiarity and productivity

## Why FastAPI for Backend?

Selected for:

- Modern Python async capabilities
- Automatic OpenAPI documentation generation
- Type hints and validation with Pydantic
- High performance with minimal boilerplate

## Why PostgreSQL for Database?

Selected for:

- Strong consistency and ACID compliance
- Advanced data types and indexing options
- Mature ecosystem and tooling
- Team experience and preference

## Why Redis/Celery for Background Jobs?

Selected for:

- Simple deployment and operation
- Reliable task queuing mechanism
- Good integration with Python ecosystem
- Support for distributed task processing

## Alternatives Considered Summary

Several alternatives were evaluated:

- Frontend: React vs Vue - Chosen Vue for team familiarity
- Backend: Django vs FastAPI - Chosen FastAPI for async capabilities
- Database: MySQL vs PostgreSQL - Chosen PostgreSQL for advanced features
- Workers: RQ vs Celery - Chosen Celery for robustness

![TO COMPLETE TAG: Reference specific ADR files where applicable]

For detailed architectural decisions, see [Architecture Decision Records](../architecture-decision-records/).
