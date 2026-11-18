# Chart values

<!-- Generated from values.yaml by `make -C helm docs`. Do not edit. -->

This page lists each value of the chart with its default. A value with
no description has only a comment in `values.yaml`. The chart
[README](README.md) tells which values an installation must set.

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| nameOverride | string | `""` |  |
| fullnameOverride | string | `""` |  |
| global.imagePullSecrets | list | `[]` | Pull secrets for all pods. Set them if your image registry is private |
| backend.enabled | bool | `true` |  |
| backend.replicaCount | int | `2` |  |
| backend.image.repository | string | `"ghcr.io/epfl-enac/epfl/co2-calculator/backend"` |  |
| backend.image.tag | string | `"latest"` | Backend image tag. Set it to one release tag, not `latest` |
| backend.image.pullPolicy | string | `"IfNotPresent"` |  |
| backend.command | list | `[]` |  |
| backend.args | list | `[]` |  |
| backend.service.type | string | `"ClusterIP"` |  |
| backend.service.port | int | `8000` |  |
| backend.service.targetPort | int | `8000` |  |
| backend.service.annotations | object | `{}` |  |
| backend.env.APP_NAME | string | `"CO2 Calculator API"` |  |
| backend.env.APP_VERSION | string | `"0.1.0"` |  |
| backend.env.DEBUG | string | `"false"` |  |
| backend.env.COOKIE_SECURE | string | `"true"` |  |
| backend.env.API_VERSION | string | `"/v1"` |  |
| backend.env.API_DOCS_PREFIX | string | `"/api"` |  |
| backend.env.LOG_LEVEL | string | `"INFO"` |  |
| backend.env.ALGORITHM | string | `"HS256"` |  |
| backend.env.ACCESS_TOKEN_EXPIRE_MINUTES | string | `"2880"` |  |
| backend.env.REFRESH_TOKEN_EXPIRE_HOURS | string | `"168"` |  |
| backend.env.ROLE_PROVIDER_TYPE | string | `"jwt"` |  |
| backend.env.UNIT_PROVIDER_TYPE | string | `"database"` |  |
| backend.env.OAUTH_SCOPE | string | `"openid profile email"` |  |
| backend.env.OAUTH_COOKIE_PATH | string | `"/"` |  |
| backend.env.FRONTEND_URL | string | `"http://localhost:3000"` |  |
| backend.env.CSRF_ADDITIONAL_ORIGINS | string | `""` |  |
| backend.env.ACCRED_AUTHORIZATION_HEALTHCHECK_URL | string | `"https://url-you-want-to-check"` |  |
| backend.env.MIN_CONFIGURABLE_YEAR | string | `"2025"` |  |
| backend.env.APP_MIN_REDUCTION_YEAR | string | `"1990"` |  |
| backend.env.APP_MAX_REDUCTION_YEAR | string | `"2050"` |  |
| backend.env.RUN_BACKGROUND_POLLER | string | `"true"` |  |
| backend.env.POLLER_INTERVAL_SECONDS | string | `"2"` |  |
| backend.env.POLLER_BATCH_LIMIT | string | `"100"` |  |
| backend.env.STALE_JOB_TIMEOUT_MINUTES | string | `"5"` |  |
| backend.env.INGEST_COPY_BATCH_SIZE | string | `"50000"` |  |
| backend.env.ELASTICSEARCH_TIMEOUT | string | `"30"` |  |
| backend.env.ELASTICSEARCH_MAX_RETRIES | string | `"3"` |  |
| backend.env.ELASTICSEARCH_RETRY_ON_TIMEOUT | string | `"true"` |  |
| backend.env.OTEL_PYTHON_DISABLED_INSTRUMENTATIONS | string | `"sqlalchemy,psycopg"` |  |
| backend.env.OTEL_TRACES_EXPORTER | string | `"none"` |  |
| backend.env.OTEL_METRICS_EXPORTER | string | `"none"` |  |
| backend.env.OTEL_LOGS_EXPORTER | string | `"none"` |  |
| backend.podAnnotations | object | `{}` |  |
| backend.podSecurityContext | string | `nil` |  |
| backend.securityContext.allowPrivilegeEscalation | bool | `false` |  |
| backend.securityContext.readOnlyRootFilesystem | bool | `true` |  |
| backend.securityContext.capabilities.drop[0] | string | `"ALL"` |  |
| backend.resources.limits.memory | string | `"512Mi"` |  |
| backend.resources.requests.cpu | int | `1` |  |
| backend.resources.requests.memory | string | `"128Mi"` |  |
| backend.livenessProbe.httpGet.path | string | `"/healthz"` |  |
| backend.livenessProbe.httpGet.port | int | `8000` |  |
| backend.livenessProbe.initialDelaySeconds | int | `30` |  |
| backend.livenessProbe.periodSeconds | int | `20` |  |
| backend.livenessProbe.timeoutSeconds | int | `5` |  |
| backend.livenessProbe.failureThreshold | int | `5` |  |
| backend.readinessProbe.httpGet.path | string | `"/ready"` |  |
| backend.readinessProbe.httpGet.port | int | `8000` |  |
| backend.readinessProbe.initialDelaySeconds | int | `10` |  |
| backend.readinessProbe.periodSeconds | int | `10` |  |
| backend.readinessProbe.timeoutSeconds | int | `3` |  |
| backend.readinessProbe.failureThreshold | int | `3` |  |
| backend.startupProbe.httpGet.path | string | `"/healthz"` |  |
| backend.startupProbe.httpGet.port | int | `8000` |  |
| backend.startupProbe.initialDelaySeconds | int | `0` |  |
| backend.startupProbe.periodSeconds | int | `2` |  |
| backend.startupProbe.failureThreshold | int | `30` |  |
| backend.autoscaling.enabled | bool | `false` |  |
| backend.autoscaling.minReplicas | int | `2` |  |
| backend.autoscaling.maxReplicas | int | `10` |  |
| backend.autoscaling.targetCPUUtilizationPercentage | int | `80` |  |
| backend.autoscaling.targetMemoryUtilizationPercentage | int | `80` |  |
| backend.podDisruptionBudget.enabled | bool | `true` |  |
| backend.podDisruptionBudget.minAvailable | int | `1` |  |
| backend.nodeSelector | object | `{}` |  |
| backend.tolerations | list | `[]` |  |
| backend.affinity | object | `{}` |  |
| backend.existingSecret.name | string | `""` | Name of the backend Secret that you create. Required. The chart README lists its keys |
| backend.existingSecret.keys.jwtHmacKeyKey | string | `"JWT_HMAC_KEY"` |  |
| backend.existingSecret.keys.sessionHmacKeyKey | string | `"SESSION_HMAC_KEY"` |  |
| backend.existingSecret.keys.oauthClientIdKey | string | `"OAUTH_CLIENT_ID"` |  |
| backend.existingSecret.keys.oauthClientSecretKey | string | `"OAUTH_CLIENT_SECRET"` |  |
| backend.existingSecret.keys.oauthIssuerUrlKey | string | `"OAUTH_ISSUER_URL"` |  |
| backend.existingSecret.keys.oauthTenantIdKey | string | `"OAUTH_TENANT_ID"` |  |
| backend.existingSecret.keys.accredApiKeyKey | string | `"ACCRED_API_KEY"` |  |
| backend.existingSecret.keys.accredApiUsernameKey | string | `"ACCRED_API_USERNAME"` |  |
| backend.existingSecret.keys.accredApiBaseUrlKey | string | `"ACCRED_API_BASE_URL"` |  |
| backend.existingSecret.keys.filesEncryptionKeyKey | string | `"FILES_ENCRYPTION_KEY"` |  |
| backend.existingSecret.keys.filesEncryptionSaltKey | string | `"FILES_ENCRYPTION_SALT"` |  |
| backend.existingSecret.keys.credentialsEncryptionKeyKey | string | `"CREDENTIALS_ENCRYPTION_KEY"` |  |
| backend.existingSecret.keys.credentialsEncryptionSaltKey | string | `"CREDENTIALS_ENCRYPTION_SALT"` |  |
| backend.existingSecret.keys.filesMaxSizeMbKey | string | `"FILES_MAX_SIZE_MB"` |  |
| backend.existingSecret.keys.s3EndpointProtocolKey | string | `"S3_ENDPOINT_PROTOCOL"` |  |
| backend.existingSecret.keys.s3EndpointHostnameKey | string | `"S3_ENDPOINT_HOSTNAME"` |  |
| backend.existingSecret.keys.s3AccessKeyIdKey | string | `"S3_ACCESS_KEY_ID"` |  |
| backend.existingSecret.keys.s3SecretAccessKeyKey | string | `"S3_SECRET_ACCESS_KEY"` |  |
| backend.existingSecret.keys.s3RegionKey | string | `"S3_REGION"` |  |
| backend.existingSecret.keys.s3BucketKey | string | `"S3_BUCKET"` |  |
| backend.existingSecret.keys.s3PathPrefixKey | string | `"S3_PATH_PREFIX"` |  |
| backend.existingSecret.keys.elasticsearchHostsKey | string | `"ELASTICSEARCH_HOSTS"` |  |
| backend.existingSecret.keys.elasticsearchIndexKey | string | `"ELASTICSEARCH_INDEX"` |  |
| backend.existingSecret.keys.elasticsearchIdKey | string | `"ELASTICSEARCH_ID"` |  |
| backend.existingSecret.keys.elasticsearchApiKeyKey | string | `"ELASTICSEARCH_API_KEY"` |  |
| backend.existingSecret.keys.elasticsearchCaCertFileKey | string | `"ELASTICSEARCH_CA_CERT_FILE"` |  |
| backend.elasticsearch.caCert.filename | string | `"http_ca_test.crt"` |  |
| backend.elasticsearch.caCert.path | string | `"/tmp/"` |  |
| backend.tableau.verifySsl | string | `"true"` |  |
| backend.tableau.requestTimeoutSeconds | string | `"300"` |  |
| backend.tableau.restMinApiVersion | string | `"2.4"` |  |
| backend.tableau.maxFields | string | `"50"` |  |
| backend.connector.allowedHostSuffixes | string | `""` |  |
| backend.initContainers.waitForPostgres.resources.limits.memory | string | `"128Mi"` |  |
| backend.initContainers.waitForPostgres.resources.requests.cpu | string | `"50m"` |  |
| backend.initContainers.waitForPostgres.resources.requests.memory | string | `"64Mi"` |  |
| backend.migrations.enabled | bool | `true` | Run the database migrations in a Job at each install and each upgrade |
| backend.migrations.resources.limits.memory | string | `"512Mi"` |  |
| backend.migrations.resources.requests.cpu | string | `"100m"` |  |
| backend.migrations.resources.requests.memory | string | `"128Mi"` |  |
| backend.migrations.waitForPostgres.resources.limits.memory | string | `"128Mi"` |  |
| backend.migrations.waitForPostgres.resources.requests.cpu | string | `"50m"` |  |
| backend.migrations.waitForPostgres.resources.requests.memory | string | `"64Mi"` |  |
| worker.enabled | bool | `false` | Run the background jobs in a separate worker Deployment |
| worker.replicaCount | int | `1` |  |
| worker.terminationGracePeriodSeconds | int | `60` |  |
| worker.autoscaling.enabled | bool | `false` |  |
| worker.autoscaling.minReplicas | int | `1` |  |
| worker.autoscaling.maxReplicas | int | `4` |  |
| worker.autoscaling.targetCPUUtilizationPercentage | int | `60` |  |
| worker.autoscaling.targetMemoryUtilizationPercentage | int | `80` |  |
| worker.env | object | `{}` | Worker env vars, merged over backend.env: a key set here wins. Set only what differs from the backend. The worker does not inherit RUN_PIPELINE_RECONCILER, so it runs the reconciler unless set here. A null value does not remove an inherited key: set "" instead. |
| worker.podAnnotations | object | `{}` |  |
| worker.resources.limits.memory | string | `"1Gi"` |  |
| worker.resources.requests.cpu | int | `2` |  |
| worker.resources.requests.memory | string | `"256Mi"` |  |
| worker.livenessProbe.httpGet.path | string | `"/healthz"` |  |
| worker.livenessProbe.httpGet.port | int | `8000` |  |
| worker.livenessProbe.initialDelaySeconds | int | `30` |  |
| worker.livenessProbe.periodSeconds | int | `20` |  |
| worker.livenessProbe.timeoutSeconds | int | `5` |  |
| worker.livenessProbe.failureThreshold | int | `5` |  |
| worker.readinessProbe.httpGet.path | string | `"/ready"` |  |
| worker.readinessProbe.httpGet.port | int | `8000` |  |
| worker.readinessProbe.initialDelaySeconds | int | `10` |  |
| worker.readinessProbe.periodSeconds | int | `10` |  |
| worker.readinessProbe.timeoutSeconds | int | `3` |  |
| worker.readinessProbe.failureThreshold | int | `3` |  |
| worker.nodeSelector | object | `{}` |  |
| worker.tolerations | list | `[]` |  |
| worker.affinity | object | `{}` |  |
| frontend.enabled | bool | `true` |  |
| frontend.replicaCount | int | `2` |  |
| frontend.image.repository | string | `"ghcr.io/epfl-enac/epfl/co2-calculator/frontend"` |  |
| frontend.image.tag | string | `"latest"` | Frontend image tag. Set it to the same release tag as the backend |
| frontend.image.pullPolicy | string | `"IfNotPresent"` |  |
| frontend.service.type | string | `"ClusterIP"` |  |
| frontend.service.port | int | `80` |  |
| frontend.service.targetPort | int | `8080` |  |
| frontend.service.annotations | object | `{}` |  |
| frontend.env.API_BASE_URL | string | `"/api"` |  |
| frontend.env.APP_SENTRY_DSN | string | `""` |  |
| frontend.env.APP_ENVIRONMENT | string | `"production"` |  |
| frontend.env.APP_ACCESS_MANAGEMENT_PROVIDER_NAME | string | `"ACCRED"` |  |
| frontend.env.APP_ACCESS_MANAGEMENT_PROVIDER_URL | string | `"https://access-management.example.com"` |  |
| frontend.env.APP_ACCESS_MANAGEMENT_PROVIDER_ABOUT_URL | string | `"https://access-management.example.com/about"` |  |
| frontend.env.APP_ROLES_DOC_URL | string | `"https://docs.example.com/roles/"` |  |
| frontend.env.APP_EQUIPMENT_POWER_FEEDBACK_EMAIL | string | `"test@epfl.ch"` |  |
| frontend.env.APP_MATOMO_URL | string | `"https://enac-webanalytics.epfl.ch/piwik/"` |  |
| frontend.env.APP_MATOMO_SITE_ID | string | `""` |  |
| frontend.env.APP_PLANNER_MIN_YEAR | string | `"2016"` |  |
| frontend.env.APP_PLANNER_MAX_YEAR | string | `"2050"` |  |
| frontend.env.APP_DEMO_MODE | string | `"false"` |  |
| frontend.env.APP_PRODUCTION_URL | string | `"https://go.epfl.ch/co2"` |  |
| frontend.podAnnotations | object | `{}` |  |
| frontend.podSecurityContext | string | `nil` |  |
| frontend.securityContext.allowPrivilegeEscalation | bool | `false` |  |
| frontend.securityContext.readOnlyRootFilesystem | bool | `true` |  |
| frontend.securityContext.capabilities.drop[0] | string | `"ALL"` |  |
| frontend.resources.limits.memory | string | `"256Mi"` |  |
| frontend.resources.requests.cpu | string | `"50m"` |  |
| frontend.resources.requests.memory | string | `"64Mi"` |  |
| frontend.livenessProbe.httpGet.path | string | `"/healthz"` |  |
| frontend.livenessProbe.httpGet.port | int | `8080` |  |
| frontend.livenessProbe.initialDelaySeconds | int | `10` |  |
| frontend.livenessProbe.periodSeconds | int | `20` |  |
| frontend.livenessProbe.timeoutSeconds | int | `5` |  |
| frontend.livenessProbe.failureThreshold | int | `5` |  |
| frontend.readinessProbe.httpGet.path | string | `"/ready"` |  |
| frontend.readinessProbe.httpGet.port | int | `8080` |  |
| frontend.readinessProbe.initialDelaySeconds | int | `5` |  |
| frontend.readinessProbe.periodSeconds | int | `10` |  |
| frontend.readinessProbe.timeoutSeconds | int | `3` |  |
| frontend.readinessProbe.failureThreshold | int | `3` |  |
| frontend.startupProbe.httpGet.path | string | `"/healthz"` |  |
| frontend.startupProbe.httpGet.port | int | `8080` |  |
| frontend.startupProbe.initialDelaySeconds | int | `0` |  |
| frontend.startupProbe.periodSeconds | int | `2` |  |
| frontend.startupProbe.failureThreshold | int | `30` |  |
| frontend.autoscaling.enabled | bool | `false` |  |
| frontend.autoscaling.minReplicas | int | `2` |  |
| frontend.autoscaling.maxReplicas | int | `10` |  |
| frontend.autoscaling.targetCPUUtilizationPercentage | int | `80` |  |
| frontend.autoscaling.targetMemoryUtilizationPercentage | int | `80` |  |
| frontend.podDisruptionBudget.enabled | bool | `true` |  |
| frontend.podDisruptionBudget.minAvailable | int | `1` |  |
| frontend.nodeSelector | object | `{}` |  |
| frontend.tolerations | list | `[]` |  |
| frontend.affinity | object | `{}` |  |
| database.existingSecret.name | string | `"db-secret"` | Name of the database Secret that you create. Required |
| database.existingSecret.keys.url | string | `"DB_URL"` | Key of the PostgreSQL URL in the database Secret. The backend and the migrations read it |
| database.existingSecret.keys.password | string | `"DB_PASSWORD"` |  |
| database.waitForPostgres.enabled | bool | `true` | Wait until PostgreSQL answers before the backend and the migrations start |
| database.waitForPostgres.image.repository | string | `"postgres"` |  |
| database.waitForPostgres.image.tag | string | `"18-alpine"` |  |
| database.waitForPostgres.image.pullPolicy | string | `"IfNotPresent"` |  |
| ingress.enabled | bool | `true` | Create an Ingress. On OpenShift, set `false` and use `routes` |
| ingress.className | string | `"nginx"` | Ingress class of your cluster |
| ingress.annotations."nginx.ingress.kubernetes.io/ssl-redirect" | string | `"true"` |  |
| ingress.annotations."nginx.ingress.kubernetes.io/force-ssl-redirect" | string | `"true"` |  |
| ingress.annotations."nginx.ingress.kubernetes.io/proxy-body-size" | string | `"50m"` |  |
| ingress.hosts | list | `["co2-calculator.local"]` | Hostnames of the app. The chart sends `/api` to the backend and `/` to the frontend |
| ingress.tls | list | `[]` | TLS entries of the Ingress |
| routes.enabled | bool | `false` | Create OpenShift Routes in place of an Ingress |
| routes.host | string | `"co2-calculator.local"` | Hostname of the Routes |
| routes.frontend.extraLabels | object | `{}` |  |
| routes.frontend.annotations | object | `{}` |  |
| routes.frontend.weight | int | `100` |  |
| routes.frontend.tls.termination | string | `"edge"` |  |
| routes.backend.extraLabels | object | `{}` |  |
| routes.backend.annotations | object | `{}` |  |
| routes.backend.weight | int | `100` |  |
| routes.backend.tls.termination | string | `"edge"` |  |
| routes.docs.enabled | bool | `true` |  |
| routes.docs.extraLabels.route | string | `"private"` |  |
| routes.docs.annotations | object | `{}` |  |
| routes.docs.weight | int | `100` |  |
| routes.docs.tls.termination | string | `"edge"` |  |
| serviceAccount.create | bool | `true` | Create a ServiceAccount for the pods |
| serviceAccount.annotations | object | `{}` |  |
| serviceAccount.name | string | `""` |  |
| serviceAccount.imagePullSecrets | list | `[]` |  |
| podDisruptionBudget.enabled | bool | `false` |  |
| podDisruptionBudget.minAvailable | int | `1` |  |
| podDisruptionBudget.maxUnavailable | string | `""` |  |
| networkPolicies.enabled | bool | `false` | Create NetworkPolicies that limit the traffic to the pods |
| networkPolicies.ingressFromRoutes | list | `[]` |  |
| docs.enabled | bool | `true` | Deploy the developer documentation site |
| docs.replicaCount | int | `1` |  |
| docs.image.repository | string | `"ghcr.io/epfl-enac/epfl/co2-calculator/docs"` |  |
| docs.image.tag | string | `"latest"` |  |
| docs.image.pullPolicy | string | `"IfNotPresent"` |  |
| docs.service.type | string | `"ClusterIP"` |  |
| docs.service.port | int | `80` |  |
| docs.service.targetPort | int | `8080` |  |
| docs.service.annotations | object | `{}` |  |
| docs.podAnnotations | object | `{}` |  |
| docs.podSecurityContext | string | `nil` |  |
| docs.securityContext.allowPrivilegeEscalation | bool | `false` |  |
| docs.securityContext.readOnlyRootFilesystem | bool | `true` |  |
| docs.securityContext.capabilities.drop[0] | string | `"ALL"` |  |
| docs.resources.limits.memory | string | `"256Mi"` |  |
| docs.resources.requests.cpu | string | `"50m"` |  |
| docs.resources.requests.memory | string | `"64Mi"` |  |
| docs.livenessProbe.httpGet.path | string | `"/"` |  |
| docs.livenessProbe.httpGet.port | int | `8080` |  |
| docs.livenessProbe.initialDelaySeconds | int | `10` |  |
| docs.livenessProbe.periodSeconds | int | `10` |  |
| docs.readinessProbe.httpGet.path | string | `"/"` |  |
| docs.readinessProbe.httpGet.port | int | `8080` |  |
| docs.readinessProbe.initialDelaySeconds | int | `5` |  |
| docs.readinessProbe.periodSeconds | int | `5` |  |
| docs.autoscaling.enabled | bool | `false` |  |
| docs.autoscaling.minReplicas | int | `1` |  |
| docs.autoscaling.maxReplicas | int | `3` |  |
| docs.autoscaling.targetCPUUtilizationPercentage | int | `80` |  |
| docs.autoscaling.targetMemoryUtilizationPercentage | int | `80` |  |
| docs.podDisruptionBudget.enabled | bool | `true` |  |
| docs.podDisruptionBudget.minAvailable | int | `1` |  |
| docs.nodeSelector | object | `{}` |  |
| docs.tolerations | list | `[]` |  |
| docs.affinity | object | `{}` |  |
