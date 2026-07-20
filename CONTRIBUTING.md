# Contributing to CO₂ Calculator

Thanks for your interest in contributing! This guide covers the essentials
to get you started quickly.

## Quick Start

New contributors follow this workflow:

1. Create or pick an issue describing your fix/feature
2. Branch from `dev`: `git checkout -b issue-123-feature-name`
3. Code with tests and documentation
4. Run `make ci` to validate locally
5. Push and create PR to `dev`
6. Address review feedback (1-2 days)
7. Merge → Auto-deploys to dev environment

**TL;DR:** `Issue → Branch → Code → Test → PR → Review → Merge`

## Development Setup

**Prerequisites:** [Node.js 24+](https://nodejs.org/), [Python 3.14+](https://www.python.org/), [Docker](https://www.docker.com/), [GNU Make](https://www.gnu.org/software/make/)

Install dependencies and start coding:

```bash
make install  # Install all dependencies
make ci       # Run all checks before pushing
```

Run services for local development:

```bash
cd backend && make dev   # Backend on :8000
cd frontend && make dev  # Frontend on :9000
```

See detailed setup in [backend](backend/README.md) and [frontend](frontend/README.md) README files.

## Commit Convention

Use conventional commits for automated changelog generation:

```
feat: add user authentication
fix: resolve database connection timeout
docs: update API documentation
test: add integration tests for payments
```

Types: `feat`, `fix`, `docs`, `test`, `refactor`, `style`, `chore`

## Pull Request Checklist

Before requesting review, ensure:

- [ ] Code follows our standards (linter passes)
- [ ] Codecov tests added/updated with 60% coverage minimum
- [ ] Documentation updated for new features
- [ ] `make ci` passes locally
- [ ] Commit messages follow convention
- [ ] PR describes what/why of changes
- [ ] No secrets or hardcoded credentials

See [PR template](.github/pull_request_template.md) for full checklist.

## Code Standards Summary

- **Never commit secrets** - Use environment variables
- **Test coverage**: 60% minimum (following Codecov reports)
- **Naming**: snake_case (Python), camelCase (JS/TS), kebab-case (files)
- **Accessibility**: WCAG Level AA for UI components
- **Dependencies**: Pin exact versions, security updates only

Full standards in [code standards](docs/src/architecture/code-standards.md)

## Need Help?

- 💬 [GitHub Discussions](https://github.com/EPFL-ENAC/co2-calculator/discussions) for questions
- 📋 [Create an issue](https://github.com/EPFL-ENAC/co2-calculator/issues/new/choose) to report bugs
- 📖 [Code of Conduct](CODE_OF_CONDUCT.md)
- 📧 Email **enacit4research@epfl.ch**

## More Documentation

- [Development Workflow](docs/src/architecture/workflow-guide.md) - Branch strategy, PR process, issue management
- [Release Management](docs/src/architecture/release-management.md) - Versioning, deployments, hotfixes
- [Code Standards](docs/src/architecture/code-standards.md) - Language guidelines, testing, dependencies
- [CI/CD Pipeline](docs/src/architecture/06-cicd-pipeline.md) - Automated checks and deployment

---

_Thank you for contributing to sustainability research at EPFL!_
