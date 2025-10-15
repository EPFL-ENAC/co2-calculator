# Infrastructure Overview

This section provides an overview of the infrastructure layer, including hosting, networking, and operational considerations.

## Infrastructure Technology

- **Platform**: Kubernetes
- **Container Runtime**: Docker
- **Orchestration**: Kubernetes with Helm charts
- **Service Mesh**: (None - direct service communication)
- **Monitoring**: Prometheus, Grafana, OpenTelemetry
- **Logging**: ELK stack or similar centralized logging
- **Secrets Management**: Kubernetes Secrets or HashiCorp Vault

## Key Components

- **Hosting Environment**: Cloud or on-premises Kubernetes clusters
- **Networking**: Internal service communication, external ingress
- **Storage**: Persistent volumes for database and file storage
- **Load Balancing**: Kubernetes services and ingress controllers
- **Security**: Network policies, TLS termination, access controls

## Integration Points

- **Application Deployment**: Helm charts and ArgoCD
- **Monitoring Systems**: Prometheus metrics collection
- **Log Aggregation**: Centralized logging infrastructure
- **Backup Systems**: Automated backup solutions
- **Alerting**: Notification systems for operational issues

## Subsystems

- [Hosting & Network](./hosting.md) - Hosting environment and networking
- [Monitoring & Logging](./monitoring.md) - Observability and logging systems

For architectural overview, see [Architecture Overview](../architecture/index.md).
