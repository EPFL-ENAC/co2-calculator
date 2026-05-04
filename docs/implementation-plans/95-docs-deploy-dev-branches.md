# Issue #95: Deploy Documentation to Kubernetes

## Overview

Implement deployment of technical documentation (MkDocs) to Kubernetes alongside the main application, enabling branch-specific documentation accessible at `/docs` sub-path.

## Problem Statement

Currently, documentation is only deployed to GitHub Pages for the main branch via `deploy-mkdocs.yml`. This doesn't support:

- Development branch documentation
- Stage/testing branch documentation
- Release-specific documentation
- Branch-based documentation testing (as requested in issue #95)

## Solution

Add documentation as a third component (alongside frontend and backend) in the existing Helm chart, deployed via the same CI/CD pipelines (`deploy.yml` and `deploy-quay.yml`).

## Implementation Details

### 1. Docker Image for Documentation

**File**: `docs/Dockerfile`

Created a simple nginx-based Docker image to serve static MkDocs site:

```dockerfile
FROM nginx:alpine
COPY . /usr/share/nginx/html
EXPOSE 8080
CMD ["nginx", "-g", "daemon off;"]
```

### 2. Helm Chart Updates

#### A. Values Configuration (`helm/values.yaml`)

Added `docs` section with:

- `enabled`: true (default)
- `replicaCount`: 1
- `image.repository`: ghcr.io/epfl-enac/epfl/co2-calculator/docs
- `image.tag`: latest (overridden by CI/CD)
- Service, resources, probes, and scaling configuration
- OpenShift routes configuration

#### B. Deployment Template (`helm/templates/docs-deployment.yaml`)

- Nginx deployment serving static documentation
- Configurable via `docs.image.repository` and `docs.image.tag`
- Health checks, security context, and resource limits
- Conditional rendering based on `docs.enabled`

#### C. Service Template (`helm/templates/docs-service.yaml`)

- ClusterIP service on port 80 → targetPort 8080
- Standard component labels and selectors

#### D. Ingress Updates (`helm/templates/ingress.yaml`)

Added `/docs` path routing:

```yaml
- path: /docs(/|$)(.*)
  pathType: ImplementationSpecific
  backend: docs service
```

Routing order:

1. `/api` → backend
2. `/docs` → docs (NEW)
3. `/` → frontend

#### E. OpenShift Routes (`helm/templates/routes.yaml`)

Added docs route when `routes.enabled` is true:

- Path: `/docs`
- Host: Same as main application
- TLS termination: edge

#### F. Helper Templates (`helm/templates/_helpers.tpl`)

Added `co2-calculator.docs.image` helper for image tag resolution.

### 3. CI/CD Pipeline Updates

#### A. `deploy.yml` (GitHub Registry)

Added `build-docs` job that:

1. Checks out code
2. Installs documentation dependencies via uv
3. Builds MkDocs site to `docs-site/`
4. Determines tag based on git ref:
   - `dev` branch → `:dev`
   - `stage` branch → `:stage`
   - `tags (v*)` → `:vX.Y.Z`
   - `ci-test/*` → `:dev`
5. Builds and pushes Docker image to `ghcr.io/epfl-enac/epfl/co2-calculator/docs:<tag>`
6. Depends on `build-docs` before running deploy job

#### B. `deploy-quay.yml` (Quay Registry)

Same as `deploy.yml` but:

- Pushes to `quay-its.epfl.ch/svc1751/co2-calculator/docs:<tag>`
- Uses Quay credentials

#### C. `deploy-mkdocs.yml` (GitHub Pages - Deprecated)

- Added prominent deprecation notice
- Keeps functionality for main branch fallback only
- Clear documentation that dev/stage/release use `/docs` path instead

### 4. Helm Chart Version

Updated `helm/Chart.yaml`:

- Version: `0.2.0` → `0.3.0`
- Description: Added "and documentation"
- Keywords: Added "documentation"

## Branch-to-Environment Mapping

| Git Ref        | Docs Image Tag | Access URL                        |
| -------------- | -------------- | --------------------------------- |
| `dev` branch   | `:dev`         | co2-calculator-dev.epfl.ch/docs   |
| `stage` branch | `:stage`       | co2-calculator-stage.epfl.ch/docs |
| `tags (v*)`    | `:vX.Y.Z`      | co2-calculator.epfl.ch/docs       |
| `ci-test/*`    | `:dev`         | co2-calculator-dev.epfl.ch/docs   |

## Files Modified

### New Files

- `docs/Dockerfile`
- `helm/templates/docs-deployment.yaml`
- `helm/templates/docs-service.yaml`

### Modified Files

- `helm/values.yaml` - Added docs configuration
- `helm/templates/ingress.yaml` - Added /docs path routing
- `helm/templates/routes.yaml` - Added docs route
- `helm/templates/_helpers.tpl` - Added docs.image helper
- `helm/templates/backend-deployment.yaml` - Added enabled conditional
- `helm/templates/frontend-deployment.yaml` - Added enabled conditional
- `helm/Chart.yaml` - Bumped version to 0.3.0
- `.github/workflows/deploy.yml` - Added build-docs job
- `.github/workflows/deploy-quay.yml` - Added build-docs job
- `.github/workflows/deploy-mkdocs.yml` - Added deprecation notice

## Usage

### Accessing Documentation

- **Dev**: Navigate to `https://co2-calculator-dev.epfl.ch/docs`
- **Stage**: Navigate to `https://co2-calculator-stage.epfl.ch/docs`
- **Release**: Navigate to `https://co2-calculator.epfl.ch/docs`

### Disabling Documentation Deployment

Set `docs.enabled: false` in Helm values if documentation deployment is not needed.

### Manual Documentation Build (Local)

```bash
cd docs
uv sync --locked --all-extras --dev
uv run mkdocs build --strict --site-dir ../docs-site
```

### Testing Documentation Locally

```bash
cd docs
uv run mkdocs serve
```

## Benefits

1. **Branch-based Documentation**: Each branch has its own documentation
2. **Version Consistency**: Docs version matches app version
3. **Single Deployment Unit**: Documentation deployed with main application
4. **Consistent Access**: All documentation at `/docs` sub-path
5. **OpenShift Compatible**: Works with both nginx ingress and OpenShift routes
6. **Fallback Available**: GitHub Pages deployment kept for main branch

## Testing Checklist

- [ ] Helm chart lint passes: `helm lint ./helm`
- [ ] Helm template renders correctly: `helm template test ./helm`
- [ ] Docs build successfully: `cd docs && make build-docs`
- [ ] Docker image builds: `docker build -t docs:test docs/`
- [ ] CI/CD pipelines build and push docs image
- [ ] Documentation accessible at `/docs` path
- [ ] Branch-specific tags deployed correctly
- [ ] OpenShift routes work when enabled

## Future Enhancements

1. **Documentation Search**: Enable mkdocs search plugin
2. **Version Picker**: Add version selector for multiple releases
3. **PDF Export**: Enable PDF generation via mkdocs-with-pdf plugin
4. **Analytics**: Add documentation usage tracking
5. **Multi-language**: Support for documentation in multiple languages

## Related Issues

- Issue #95: "Docs of each branch available for testing"

## Notes

- The documentation is served via nginx in a lightweight container
- Image tag is dynamically set by CI/CD based on git ref
- Helm chart uses `latest` as default tag, overridden by ArgoCD
- Documentation build uses the same MkDocs configuration as before
- No changes to documentation content or structure
