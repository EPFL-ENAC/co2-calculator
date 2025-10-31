# Adding a PostgreSQL Sidekick to the CO2 Calculator Chart

The Helm chart expects an external PostgreSQL instance, but you can co-locate a database in the same namespace when necessary. The approaches below highlight supported, Kubernetes-friendly options and how to wire their connection details back into the CO2 Calculator release.

> ⚠️ **Warning**: Running PostgreSQL inside the application cluster introduces additional operational duties (backups, PITR, failover, storage management). Prefer managed services in production.

## Option 1 – Bitnami PostgreSQL Chart (Fastest)

1. **Add the repository and install**

   ```bash
   helm repo add bitnami https://charts.bitnami.com/bitnami
   helm repo update

   helm upgrade --install co2-postgres bitnami/postgresql \
     --set auth.username=co2user \
     --set auth.password=super-secret \
     --set auth.database=co2_calculator \
     --set primary.persistence.size=10Gi
   ```

2. **Retrieve credentials**

   ```bash
   export POSTGRES_PASSWORD=$(kubectl get secret co2-postgres-postgresql -o jsonpath='{.data.password}' | base64 -d)
   ```

3. **Update your CO2 Calculator values file**

   ```yaml
   database:
   external:
     host: "co2-postgres-postgresql"
     port: 5432
     database: "co2_calculator"
     username: "co2user"
     password: "${POSTGRES_PASSWORD}"
   ```

4. **Optional: enable PgBouncer** by setting `pgbouncer.enabled=true` if you expect spiky connection patterns.

## Option 2 – CloudNativePG Operator (Production-grade)

1. **Install the operator**

   ```bash
   kubectl apply -f https://raw.githubusercontent.com/cloudnative-pg/cloudnative-pg/release-1.22/releases/cnpg-1.22.0.yaml
   ```

2. **Create a credentials secret**

   ```bash
   kubectl create secret generic co2-postgres-credentials \
     --from-literal=username=co2user \
     --from-literal=password=super-secret
   ```

3. **Deploy a cluster manifest** (`postgres-cluster.yaml`):

   ```yaml
   apiVersion: postgresql.cnpg.io/v1
   kind: Cluster
   metadata:
     name: co2-postgres
   spec:
     instances: 3
     storage:
       size: 20Gi
     bootstrap:
       initdb:
         database: co2_calculator
         owner: co2user
         secret:
           name: co2-postgres-credentials
   ```

   ```bash
   kubectl apply -f postgres-cluster.yaml
   kubectl wait --for=condition=Ready cluster/co2-postgres --timeout=600s
   ```

4. **Connect the application**
   ```yaml
   database:
   external:
     host: "co2-postgres-rw"
     port: 5432
     database: "co2_calculator"
     username: "co2user"
     password: "super-secret"
   ```
   Use `co2-postgres-ro` for read-only workloads if desired.

## Option 3 – Other PostgreSQL Operators

Projects such as Zalando Postgres Operator or Crunchy Data PGO provide managed controllers with high availability and backup automation. Follow their installation guides and surface host/user/password credentials via Kubernetes secrets, referencing them through `database.externalSecret` in the CO2 Calculator chart.

## Feeding Credentials Back to the Chart

Regardless of the chosen deployment method, expose connection details with one of the chart mechanisms:

- **Direct values** in `database.external` and `backend.secrets.SECRET_KEY`.
- **Kubernetes secret** containing `DB_USER`, and `DB_PASSWORD`, referenced by `database.externalSecret` and `backend.externalSecret`.
- When PgBouncer is enabled, the chart rewrites `DB_HOST` automatically to point to the PgBouncer service name (`<release>-pgbouncer`).

## Clean-up

Remove the sidekick resources before tearing down persistent volumes:

```bash
helm uninstall co2-calculator
helm uninstall co2-postgres   # Bitnami
kubectl delete cluster co2-postgres  # CloudNativePG
```

Always confirm PVC deletion and snapshot posture to avoid orphaned storage.
