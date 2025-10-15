# CI/CD Pipeline Overview

![TO COMPLETE TAG: Include pipeline architecture diagram] ??? maybe

The continuous integration and deployment pipeline automates the build, test, and deployment processes across all environments.

## Build Process per Subsystem

Each subsystem has its own build process:

- Frontend: Node.js build with vite
- Backend: Python package with dependencies
- Infrastructure: Kubernetes manifests

## Deployment Automation Flow

Deployments are fully automated through GitHub Actions:

1. Code changes trigger CI pipeline
2. Tests are run in isolated environments
3. Artifacts are built and stored in github public registry (ghcr.io)
4. Our action modify our infra code (EPFL-ENAC/epfl-enac-build-push-deploy-action)
5. ArgoCD handles deployment to Kubernetes clusters

## Performance + EcoConception

- LighthouseCI + greenIT

## DevSecOps + Testing Integration Points

Automated testing includes:

- Unit tests for individual components
- Integration tests for subsystem interactions
- End-to-end tests for critical user flows
- Security scans and vulnerability assessments

## Rollback Mechanisms

Rollbacks are supported through:

- Kubernetes deployment history (git-ops)
- Database migration versioning
