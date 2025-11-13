# Infrastructure Overview

The infrastructure runs on EPFL's Kubernetes platform (ENAC-K8S) with PostgreSQL for persistence and monitoring via Prometheus/Grafana. This overview covers deployment, hosting, and operational procedures.

For system architecture and deployment decisions, see:

- [Deployment Topology](../architecture/11-deployment-topology.md) - Infrastructure architecture
- [Environments](../architecture/05-environments.md) - Environment configuration
- [CI/CD Pipeline](../architecture/06-cicd-pipeline.md) - Automated deployment
- [Tech Stack](../architecture/08-tech-stack.md) - Infrastructure technology choices

---

## Infrastructure Overview

### Platform

- **Kubernetes**: EPFL internal cluster (ENAC-K8S)
- **Container Runtime**: Docker
- **Orchestration**: Kubernetes with Helm charts
- **Load Balancing**: EPFL load balancer (internal only, not publicly accessible)
- **Storage**: RCP NAS for persistent volumes
- **Monitoring**: Prometheus, Grafana, OpenTelemetry
- **Secrets Management**: Infisical
- **Deployment**: ArgoCD (GitOps) + GitHub Actions

### Network Architecture

```
Internet
  ↓
EPFL VPN (required for external access)
  ↓
EPFL Load Balancer (internal only)
  ↓
Kubernetes Ingress Controller
  ↓
Services (frontend, backend, database)
```

**Access**: Application is **NOT publicly accessible** outside EPFL network. Users must connect via EPFL VPN or be on EPFL campus network.

---

## Deployment

### Helm Chart Structure

```
helm/
├── Chart.yaml              # Chart metadata
├── values.yaml             # Default configuration
├── values-dev.yaml         # Development overrides
├── values-staging.yaml     # Staging overrides
├── values-prod.yaml        # Production overrides
└── templates/
    ├── frontend-deployment.yaml
    ├── backend-deployment.yaml
    ├── postgres-statefulset.yaml
    ├── redis-deployment.yaml
    ├── celery-deployment.yaml
    ├── ingress.yaml
    ├── services.yaml
    ├── configmaps.yaml
    └── secrets.yaml (managed by Infisical)
```

### Deploying to Environments

**Via ArgoCD** (Recommended):

ArgoCD automatically syncs from Git repository to Kubernetes cluster.

```bash
# View ArgoCD applications
argocd app list

# Sync application manually
argocd app sync co2-calculator-dev

# View deployment status
argocd app get co2-calculator-dev
```

**Via Helm** (Manual):

```bash
# Deploy to development
helm upgrade --install co2-calculator ./helm \
  --namespace co2-calculator-dev \
  --values helm/values-dev.yaml

# Deploy to staging
helm upgrade --install co2-calculator ./helm \
  --namespace co2-calculator-staging \
  --values helm/values-staging.yaml

# Deploy to production
helm upgrade --install co2-calculator ./helm \
  --namespace co2-calculator-prod \
  --values helm/values-prod.yaml
```

### Deployment Checklist

Before deploying to production:

- [ ] All tests pass in CI/CD pipeline
- [ ] Staging deployment tested and validated
- [ ] Database migrations reviewed and tested
- [ ] Environment variables configured correctly
- [ ] Secrets rotated if needed
- [ ] Monitoring dashboards ready
- [ ] Rollback plan documented
- [ ] Stakeholders notified of deployment window

---

## Kubernetes Resources

### Namespaces

- `co2-calculator-dev`: Development environment
- `co2-calculator-staging`: Staging environment
- `co2-calculator-prod`: Production environment

### Deployments

```yaml
# Frontend (Nginx + Vue SPA)
frontend:
  replicas: 2
  resources:
    requests: { cpu: 100m, memory: 128Mi }
    limits: { cpu: 500m, memory: 256Mi }

# Backend (FastAPI + Uvicorn)
backend:
  replicas: 3
  resources:
    requests: { cpu: 200m, memory: 512Mi }
    limits: { cpu: 1000m, memory: 1Gi }

# Celery Workers
celery-worker:
  replicas: 2
  resources:
    requests: { cpu: 200m, memory: 512Mi }
    limits: { cpu: 1000m, memory: 2Gi }

# Redis (task queue)
redis:
  replicas: 1
  resources:
    requests: { cpu: 100m, memory: 256Mi }
    limits: { cpu: 500m, memory: 512Mi }
```

### StatefulSet

```yaml
# PostgreSQL
postgres:
  replicas: 1
  storage: 50Gi # RCP NAS persistent volume
  resources:
    requests: { cpu: 500m, memory: 1Gi }
    limits: { cpu: 2000m, memory: 4Gi }
```

### Services

```yaml
# Service definitions
frontend-service:
  type: ClusterIP
  port: 80

backend-service:
  type: ClusterIP
  port: 8000

postgres-service:
  type: ClusterIP
  port: 5432

redis-service:
  type: ClusterIP
  port: 6379
```

### Ingress

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: co2-calculator-ingress
  annotations:
    kubernetes.io/ingress.class: nginx
    cert-manager.io/cluster-issuer: letsencrypt-prod
spec:
  tls:
    - hosts:
        - co2calculator.epfl.ch
      secretName: co2calculator-tls
  rules:
    - host: co2calculator.epfl.ch
      http:
        paths:
          - path: /api
            pathType: Prefix
            backend:
              service:
                name: backend-service
                port: 8000
          - path: /
            pathType: Prefix
            backend:
              service:
                name: frontend-service
                port: 80
```

---

## Configuration Management

### ConfigMaps

```yaml
# Application configuration (non-sensitive)
apiVersion: v1
kind: ConfigMap
metadata:
  name: backend-config
data:
  DATABASE_HOST: postgres-service
  DATABASE_PORT: "5432"
  DATABASE_NAME: co2calculator
  REDIS_HOST: redis-service
  REDIS_PORT: "6379"
  LOG_LEVEL: INFO
  CORS_ORIGINS: https://co2calculator.epfl.ch
```

### Secrets (Infisical)

Secrets are managed via Infisical and injected into pods:

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: backend-secrets
type: Opaque
data:
  DATABASE_PASSWORD: <base64-encoded>
  SECRET_KEY: <base64-encoded>
  OIDC_CLIENT_SECRET: <base64-encoded>
```

**Management**:

```bash
# View secrets (requires cluster admin access)
kubectl get secrets -n co2-calculator-prod

# Describe secret (no values shown)
kubectl describe secret backend-secrets -n co2-calculator-prod

# Rotate secret
# Update in Infisical → ArgoCD auto-syncs → Restart deployment
kubectl rollout restart deployment backend -n co2-calculator-prod
```

---

## Storage

### Persistent Volumes

```yaml
# PostgreSQL persistent volume claim
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: postgres-pvc
spec:
  accessModes:
    - ReadWriteOnce
  storageClassName: rcp-nas # EPFL RCP NAS storage
  resources:
    requests:
      storage: 50Gi
```

### Storage Classes

- **rcp-nas**: RCP NAS storage (default, for database)
- **local-path**: Local node storage (for temporary files)

### Backup Storage

- **Database backups**: RCP NAS (`/backups/postgres/`)
- **Application files**: RCP NAS (`/data/uploads/`)
- **Long-term archives**: EPFL S3-compatible storage (if configured)

---

## Monitoring & Observability

### Prometheus Metrics

**Backend metrics** (`/metrics` endpoint):

```
# Request metrics
http_requests_total{method="GET", endpoint="/api/v1/labs", status="200"}
http_request_duration_seconds_bucket{le="0.1"}

# Application metrics
db_connections_active
db_query_duration_seconds
celery_tasks_running
celery_tasks_failed_total

# Resource metrics
process_cpu_seconds_total
process_resident_memory_bytes
```

**Scrape configuration**:

```yaml
# prometheus-config
scrape_configs:
  - job_name: "co2-calculator-backend"
    kubernetes_sd_configs:
      - role: pod
    relabel_configs:
      - source_labels: [__meta_kubernetes_pod_label_app]
        regex: backend
        action: keep
```

### Grafana Dashboards

**Main Dashboards**:

1. **Application Overview**
   - Request rate, latency, error rate
   - Active users, database connections
   - Celery queue length, task processing time

2. **Infrastructure Health**
   - CPU, memory, disk usage per pod
   - Network I/O, request throughput
   - Pod restart count, OOMKills

3. **Database Performance**
   - Query duration, slow queries
   - Connection pool usage
   - Table sizes, index usage

**Access**: https://grafana.epfl.ch (requires EPFL credentials)

### Alerting

**Critical Alerts** (PagerDuty/email):

- Service down (all replicas unhealthy)
- Database connection failure
- Disk space > 90%
- Error rate > 5% for 5 minutes

**Warning Alerts** (Slack/email):

- High memory usage (> 80%)
- Slow response time (> 1s p95)
- Celery queue backlog (> 1000 tasks)
- Certificate expiry (< 7 days)

**Configuration**: Alert rules defined in `helm/templates/prometheus-rules.yaml`

### Logging

**Log Aggregation**: Logs sent to centralized logging (ELK or similar)

```bash
# View pod logs
kubectl logs -n co2-calculator-prod deployment/backend --tail=100 -f

# View logs from all backend replicas
kubectl logs -n co2-calculator-prod -l app=backend --tail=50

# Search logs (if Kibana available)
# Access Kibana UI and filter by namespace: co2-calculator-prod
```

**Log Format**: Structured JSON logs

```json
{
  "timestamp": "2025-11-11T10:15:30Z",
  "level": "INFO",
  "logger": "app.services.labs",
  "message": "Laboratory created",
  "lab_id": "abc123",
  "user_id": "user456",
  "trace_id": "xyz789"
}
```

---

## Scaling

### Horizontal Pod Autoscaler (HPA)

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: backend-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: backend
  minReplicas: 3
  maxReplicas: 10
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
    - type: Resource
      resource:
        name: memory
        target:
          type: Utilization
          averageUtilization: 80
```

**Trigger**: Auto-scales when CPU > 70% or memory > 80%

### Manual Scaling

```bash
# Scale backend replicas
kubectl scale deployment backend --replicas=5 -n co2-calculator-prod

# Scale Celery workers
kubectl scale deployment celery-worker --replicas=4 -n co2-calculator-prod
```

---

## Operations

### Common kubectl Commands

```bash
# View all resources in namespace
kubectl get all -n co2-calculator-prod

# Check pod status
kubectl get pods -n co2-calculator-prod

# Describe pod (troubleshooting)
kubectl describe pod backend-xxxxx -n co2-calculator-prod

# View pod logs
kubectl logs backend-xxxxx -n co2-calculator-prod

# Execute command in pod
kubectl exec -it backend-xxxxx -n co2-calculator-prod -- /bin/bash

# Port forward for local access
kubectl port-forward svc/backend-service 8000:8000 -n co2-calculator-prod

# Restart deployment
kubectl rollout restart deployment backend -n co2-calculator-prod

# View rollout status
kubectl rollout status deployment backend -n co2-calculator-prod

# Rollback deployment
kubectl rollout undo deployment backend -n co2-calculator-prod
```

### Health Checks

```bash
# Check ingress
kubectl get ingress -n co2-calculator-prod

# Test backend health endpoint
curl https://co2calculator.epfl.ch/api/health

# Test from inside cluster
kubectl run -it --rm debug --image=curlimages/curl --restart=Never -n co2-calculator-prod -- \
  curl http://backend-service:8000/health
```

### Database Operations

```bash
# Connect to PostgreSQL
kubectl exec -it postgres-0 -n co2-calculator-prod -- psql -U postgres -d co2calculator

# Backup database
kubectl exec postgres-0 -n co2-calculator-prod -- \
  pg_dump -U postgres co2calculator > backup_$(date +%Y%m%d).sql

# Restore database
kubectl exec -i postgres-0 -n co2-calculator-prod -- \
  psql -U postgres co2calculator < backup.sql
```

---

## Troubleshooting

### Pod Not Starting

```bash
# Check pod events
kubectl describe pod backend-xxxxx -n co2-calculator-prod

# Common issues:
# - ImagePullBackOff: Check image name/tag, registry credentials
# - CrashLoopBackOff: Check logs, environment variables
# - Pending: Check resource requests, node capacity
```

### Service Not Reachable

```bash
# Check service endpoints
kubectl get endpoints backend-service -n co2-calculator-prod

# Check ingress configuration
kubectl describe ingress co2-calculator-ingress -n co2-calculator-prod

# Test service from inside cluster
kubectl run -it --rm test --image=curlimages/curl --restart=Never -n co2-calculator-prod -- \
  curl http://backend-service:8000/health
```

### Database Connection Issues

```bash
# Check PostgreSQL pod status
kubectl get pod postgres-0 -n co2-calculator-prod

# Check PostgreSQL logs
kubectl logs postgres-0 -n co2-calculator-prod

# Test connection from backend pod
kubectl exec -it backend-xxxxx -n co2-calculator-prod -- \
  psql postgresql://postgres:password@postgres-service:5432/co2calculator -c "SELECT 1;"
```

### High Resource Usage

```bash
# Check resource usage
kubectl top pods -n co2-calculator-prod

# Check resource limits
kubectl describe pod backend-xxxxx -n co2-calculator-prod | grep -A 5 "Limits"

# View historical metrics in Grafana
# Or use kubectl metrics (if metrics-server installed)
```

---

## Security

### Network Policies

```yaml
# Restrict backend to only accept traffic from frontend and ingress
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: backend-network-policy
spec:
  podSelector:
    matchLabels:
      app: backend
  policyTypes:
    - Ingress
  ingress:
    - from:
        - podSelector:
            matchLabels:
              app: frontend
        - podSelector:
            matchLabels:
              app: ingress-nginx
      ports:
        - protocol: TCP
          port: 8000
```

### Pod Security

- **Run as non-root**: All containers run as non-root user
- **Read-only filesystem**: Containers have read-only root filesystem where possible
- **Drop capabilities**: Unnecessary Linux capabilities dropped
- **Resource limits**: CPU and memory limits enforced

### TLS/SSL

- **Certificate management**: cert-manager with Let's Encrypt
- **TLS termination**: At ingress controller
- **Internal communication**: Unencrypted (within cluster network)

---

## Additional Resources

### Architecture Documentation

- [Deployment Topology](../architecture/11-deployment-topology.md) - Full deployment architecture
- [Scalability Strategy](../architecture/12-scalability.md) - Scaling patterns
- [CI/CD Pipeline](../architecture/06-cicd-pipeline.md) - Deployment automation

### EPFL Resources

- EPFL Kubernetes Documentation (internal)
- ENAC-IT Support (for infrastructure issues)
- RCP NAS Documentation (for storage)

### External Documentation

- [Kubernetes Documentation](https://kubernetes.io/docs/)
- [Helm Documentation](https://helm.sh/docs/)
- [ArgoCD Documentation](https://argo-cd.readthedocs.io/)
- [Prometheus Documentation](https://prometheus.io/docs/)

---

**Last Updated**: November 11, 2025  
**Readable in**: ~10 minutes
