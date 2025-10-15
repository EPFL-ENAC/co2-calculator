# Deployment Topology

## Docker Compose (Local/Staging)

Local development uses Docker Compose for simplified service orchestration:

- Single docker-compose.yml file
- Shared network for service communication
- Volume mounts for data persistence

## Kubernetes Cluster (Production)

Production deployments use Kubernetes for scalability and reliability:

- Helm charts for service deployment
- ArgoCD for GitOps deployment management
- Ingress controllers for external access

### Service Mesh Overview

Currently not using a service mesh, but may adopt Istio in the future for:

- Enhanced observability
- Traffic management
- Security policies

### Ingress and Networking Patterns

- EPFL LOAD BALANCER
- NGINX ingress controller for HTTP routing
- TLS termination at ingress level
- Network policies for service isolation

![TO COMPLETE TAG: Deployment diagrams for both setups]

For detailed deployment information, see [Infrastructure Documentation](../infra/hosting.md).
