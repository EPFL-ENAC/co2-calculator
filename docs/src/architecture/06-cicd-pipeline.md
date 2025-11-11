# CI/CD Pipeline

The continuous integration and deployment pipeline automates build,
test, security scanning, and deployment across all environments.

## Pipeline Overview

All pull requests and merges trigger GitHub Actions workflows that
validate code quality before deployment.

```
PR Created → CI Checks → Review → Merge → Build → Deploy → Monitor
```

## Automated Checks

### Linting and Formatting

Code style is enforced automatically:

**Python:**

- `ruff` - Fast linting for style violations
- `black` - Code formatting verification
- `mypy` - Static type checking

**JavaScript/TypeScript:**

- `eslint` - Linting with project rules
- `prettier` - Formatting verification
- `typescript` - Type checking

All checks must pass before merge is allowed.

### Testing

Full test suite runs on every PR:

**Backend tests:**

- Unit tests with `pytest`
- Integration tests for API endpoints
- Test coverage minimum: 60%

**Frontend tests:**

- Component tests with Vitest
- E2E tests with Playwright (critical flows)
- Test coverage minimum: 60%

Run locally before pushing: `make test`

### Security Scanning

Multiple security checks protect the codebase:

**Dependency scanning:**

- `uv pip audit` - Python vulnerability scan
- `npm audit` - Node.js vulnerability scan
- Dependabot alerts for both ecosystems

**Code scanning:**

- CodeQL analysis for security vulnerabilities
- Secret scanning to prevent credential leaks
- SAST (Static Application Security Testing)

**Container scanning:**

- Docker image vulnerability scan
- Base image updates via Dependabot

Critical vulnerabilities block merge until resolved.

### Build Validation

Verify builds succeed before deployment:

**Backend:**

```bash
cd backend && make build
# Creates Docker image
```

**Frontend:**

```bash
cd frontend && make build
# Creates production bundle with Vite
```

Build failures prevent deployment to any environment.

## Merge Requirements

Pull requests must meet these criteria before merge:

- [ ] All CI checks passing (green status)
- [ ] Code review approved by team member
- [ ] Test coverage at 60% minimum
- [ ] No critical security vulnerabilities
- [ ] Dependabot alerts resolved or acknowledged
- [ ] Conventional commit messages

Merge is blocked automatically if requirements are not met.

## Deployment Pipeline

### Build Process per Subsystem

Each component builds independently:

**Frontend:**

- Node.js build with Vite bundler
- Static assets optimized and compressed
- Source maps generated for debugging
- Environment variables injected

**Backend:**

- Python package with uv dependencies
- Docker image with multi-stage build
- Health check endpoint verified
- Database migrations included

**Infrastructure:**

- Kubernetes manifests generated
- Helm charts validated
- Config maps and secrets prepared

### Deployment Flow

Automated deployment follows this sequence:

1. **Trigger** - Merge to `dev`, `stage`, or `main` branch
2. **Build** - GitHub Actions builds Docker images
3. **Push** - Images pushed to ghcr.io registry
4. **Update** - EPFL-ENAC/epfl-enac-build-push-deploy-action updates infra repo
5. **Sync** - ArgoCD detects changes and deploys to Kubernetes
6. **Verify** - Health checks confirm successful deployment

**Environment deployment rules:**

| Branch  | Environment   | Trigger            | Validation          |
| ------- | ------------- | ------------------ | ------------------- |
| `dev`   | Development   | Automatic on merge | Smoke tests         |
| `stage` | Staging       | Manual PR approval | Full regression     |
| `main`  | Pre-prod/Prod | Manual with tag    | Complete validation |

### Deployment Artifacts

Artifacts are versioned and stored:

- Docker images: `ghcr.io/epfl-enac/co2-calculator-backend:v0.1.0`
- Frontend bundles: `ghcr.io/epfl-enac/co2-calculator-frontend:v0.1.0`
- Helm charts: Tagged in git with version
- Database migrations: Included in backend image

Artifacts are immutable and tagged with version.

## Performance Monitoring

### LighthouseCI

Frontend performance is tracked automatically:

- Performance score > 90
- Accessibility score > 90
- Best practices score > 90
- SEO score > 90

Reports generated on each deployment.

### EcoConception

Green IT metrics monitored:

- Page weight < 1MB target
- HTTP requests minimized
- Energy efficiency tracked
- Carbon footprint estimated

### Backend Performance

Optional load testing for backend:

- Response time < 500ms (p95)
- Throughput > 100 req/s
- Error rate < 0.1%

Run with k6 or locust when needed.

## Rollback Mechanisms

If deployment issues occur, rollback is automated:

**Kubernetes rollback:**

```bash
argocd app rollback co2-calculator
```

ArgoCD maintains deployment history using git-ops pattern.

**Database rollback:**

```bash
cd backend && make migration-down
```

Alembic migrations include downgrade scripts.

**Manual rollback:**

```bash
# Revert to previous version tag
git checkout v0.2.0
kubectl set image deployment/backend backend=ghcr.io/...:v0.2.0
```

Always test rollback procedures in staging first.

## CI/CD Workflows

### Workflow Files

GitHub Actions workflows in `.github/workflows/`:

- `ci.yml` - Runs on all PRs (lint, test, build)
- `security.yml` - Security scans (daily + on PR)
- `deploy-dev.yml` - Auto-deploy to dev
- `deploy-stage.yml` - Manual deploy to staging
- `deploy-prod.yml` - Tagged release to production
- `release-please.yml` - Automated changelog

### Local CI Validation

Run full CI suite locally before pushing:

```bash
make ci  # Runs lint, type-check, test, build
```

This matches GitHub Actions checks exactly.

## Monitoring and Alerts

Post-deployment monitoring:

**Application metrics:**

- Error rates in logs
- Response times
- Request volumes
- Resource usage

**Infrastructure metrics:**

- Pod health status
- Container restarts
- Resource limits
- Network traffic

**Alerting rules:**

- Error rate > 1%
- Response time > 2s
- Pod crashes
- Failed deployments

Alerts sent to team via configured channels.

## DevSecOps Integration

Security is integrated throughout the pipeline:

**Shift-left security:**

- Pre-commit hooks run basic checks
- IDE extensions show issues in real-time
- PR checks catch problems early

**Continuous scanning:**

- Daily dependency scans
- Weekly container scans
- Code scanning on every commit

**Vulnerability response:**

- Critical: Fix within 24 hours
- High: Fix within 7 days
- Medium: Fix within 30 days
- Low: Fix at next sprint

See [Code Standards](code-standards.md) for security policies.

## Continuous Improvement

Pipeline metrics tracked:

- Build success rate
- Average build time
- Deployment frequency
- Mean time to recovery
- Change failure rate

Review monthly to optimize processes.
