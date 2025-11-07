# Infrastructure Overview

This section provides an overview of the infrastructure layer, including hosting, networking, and operational considerations.

## Infrastructure Technology

- **Platform**: Kubernetes
- **Container Runtime**: Docker
- **Orchestration**: Kubernetes with Helm charts
- **Service Mesh**: (None - direct service communication)
- **Monitoring**: Prometheus, Grafana, OpenTelemetry
- **Logging**: ELK stack or similar centralized logging
- **Secrets Management**: Infisical

## Key Components

- **Hosting Environment**: On-premises Kubernetes clusters (ENAC-K8S)
- **Networking**: EPFL internal load-balancer (not available outside epfl)
- **Storage**: Persistent volumes (RCP NAS) for database and file storage
- **Load Balancing**: EPFL + Kubernetes services and ingress controllers
- **Security**: Network policies, TLS termination, access controls (EPFL standard)

## Integration Points

- **Application Deployment**: Helm charts and ArgoCD
- **Monitoring Systems**: Prometheus metrics collection
- **Log Aggregation**: Centralized logging infrastructure
- **Backup Systems**: Automated backup solutions (ENAC-IT + EPFL VM + RCP NAS)
  - TBDefined a bit more ?
- **Alerting**: Notification systems for operational issues

## Subsystems

- [Hosting & Network](./hosting.md) - Hosting environment and networking
- [Monitoring & Logging](./monitoring.md) - Observability and logging systems

For architectural overview, see [Architecture Overview](../architecture/index.md).
