{{- define "co2-calculator.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "co2-calculator.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- $name := default .Chart.Name .Values.nameOverride -}}
{{- if contains $name .Release.Name -}}
{{- .Release.Name | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}
{{- end -}}

{{- define "co2-calculator.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "co2-calculator.labels" -}}
helm.sh/chart: {{ include "co2-calculator.chart" . }}
{{ include "co2-calculator.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end -}}

{{- define "co2-calculator.selectorLabels" -}}
app.kubernetes.io/name: {{ include "co2-calculator.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{- define "co2-calculator.componentLabels" -}}
{{ include "co2-calculator.labels" .ctx }}
app.kubernetes.io/component: {{ .component }}
{{- end -}}

{{- define "co2-calculator.componentSelectorLabels" -}}
{{ include "co2-calculator.selectorLabels" .ctx }}
app.kubernetes.io/component: {{ .component }}
{{- end -}}

{{- define "co2-calculator.backend.image" -}}
{{- $tag := .Values.backend.image.tag | default .Chart.AppVersion -}}
{{- printf "%s:%s" .Values.backend.image.repository $tag -}}
{{- end -}}

{{- define "co2-calculator.frontend.image" -}}
{{- $tag := .Values.frontend.image.tag | default .Chart.AppVersion -}}
{{- printf "%s:%s" .Values.frontend.image.repository $tag -}}
{{- end -}}

{{- define "co2-calculator.docs.image" -}}
{{- $tag := .Values.docs.image.tag | default .Chart.AppVersion -}}
{{- printf "%s:%s" .Values.docs.image.repository $tag -}}
{{- end -}}

{{- define "co2-calculator.backendSecretName" -}}
{{- if .Values.backend.existingSecret.enabled -}}
{{- required "backend.existingSecret.enabled=true but backend.existingSecret.name is empty. Set it to your pre-existing Secret's name, or set backend.existingSecret.enabled=false to use a chart-managed secret." .Values.backend.existingSecret.name -}}
{{- else -}}
{{ include "co2-calculator.fullname" . }}-backend
{{- end -}}
{{- end -}}

{{- define "co2-calculator.serviceAccountName" -}}
{{- if .Values.serviceAccount.create -}}
{{- default (include "co2-calculator.fullname" .) .Values.serviceAccount.name -}}
{{- else -}}
{{- default "default" .Values.serviceAccount.name -}}
{{- end -}}
{{- end -}}

{{/*
Database secret name
Returns the name of the secret containing database credentials
*/}}
{{- define "co2-calculator.databaseSecretName" -}}
{{- .Values.database.existingSecret.name -}}
{{- end -}}

{{/*
Shared env vars for any pod running the backend image (DB URL, every
secretKeyRef-backed credential, Tableau/connector/Elasticsearch-CA config,
pod identity, OTEL resource attributes). Plan #2050 Track B: extracted out
of backend-deployment.yaml so the worker deployment gets the exact same
values with no risk of drifting out of sync — both need the full
credential set, just a different per-deployment `env` map (RUN_BACKGROUND_
POLLER / DISPATCH_JOBS_INLINE) layered on top by the caller.
*/}}
{{- define "co2-calculator.backendSecretEnv" -}}
- name: DB_URL
  valueFrom:
    secretKeyRef:
      name: {{ include "co2-calculator.databaseSecretName" . }}
      key: {{ .Values.database.existingSecret.keys.url }}
- name: JWT_HMAC_KEY
  valueFrom:
    secretKeyRef:
      name: {{ include "co2-calculator.backendSecretName" . }}
      key: {{ .Values.backend.existingSecret.keys.jwtHmacKeyKey | default "JWT_HMAC_KEY" }}
- name: SESSION_HMAC_KEY
  valueFrom:
    secretKeyRef:
      name: {{ include "co2-calculator.backendSecretName" . }}
      key: {{ .Values.backend.existingSecret.keys.sessionHmacKeyKey | default "SESSION_HMAC_KEY" }}
- name: OAUTH_CLIENT_ID
  valueFrom:
    secretKeyRef:
      name: {{ include "co2-calculator.backendSecretName" . }}
      key: {{ .Values.backend.existingSecret.keys.oauthClientIdKey | default "OAUTH_CLIENT_ID" }}
- name: OAUTH_CLIENT_SECRET
  valueFrom:
    secretKeyRef:
      name: {{ include "co2-calculator.backendSecretName" . }}
      key: {{ .Values.backend.existingSecret.keys.oauthClientSecretKey | default "OAUTH_CLIENT_SECRET" }}
- name: OAUTH_ISSUER_URL
  valueFrom:
    secretKeyRef:
      name: {{ include "co2-calculator.backendSecretName" . }}
      key: {{ .Values.backend.existingSecret.keys.oauthIssuerUrlKey | default "OAUTH_ISSUER_URL" }}
- name: OAUTH_TENANT_ID
  valueFrom:
    secretKeyRef:
      name: {{ include "co2-calculator.backendSecretName" . }}
      key: {{ .Values.backend.existingSecret.keys.oauthTenantIdKey | default "OAUTH_TENANT_ID" }}
- name: ACCRED_API_KEY
  valueFrom:
    secretKeyRef:
      name: {{ include "co2-calculator.backendSecretName" . }}
      key: {{ .Values.backend.existingSecret.keys.accredApiKeyKey | default "ACCRED_API_KEY" }}
- name: ACCRED_API_USERNAME
  valueFrom:
    secretKeyRef:
      name: {{ include "co2-calculator.backendSecretName" . }}
      key: {{ .Values.backend.existingSecret.keys.accredApiUsernameKey | default "ACCRED_API_USERNAME" }}
- name: ACCRED_API_BASE_URL
  valueFrom:
    secretKeyRef:
      name: {{ include "co2-calculator.backendSecretName" . }}
      key: {{ .Values.backend.existingSecret.keys.accredApiBaseUrlKey | default "ACCRED_API_BASE_URL" }}
- name: FILES_ENCRYPTION_KEY
  valueFrom:
    secretKeyRef:
      name: {{ include "co2-calculator.backendSecretName" . }}
      key: {{ .Values.backend.existingSecret.keys.filesEncryptionKeyKey | default "FILES_ENCRYPTION_KEY" }}
- name: FILES_ENCRYPTION_SALT
  valueFrom:
    secretKeyRef:
      name: {{ include "co2-calculator.backendSecretName" . }}
      key: {{ .Values.backend.existingSecret.keys.filesEncryptionSaltKey | default "FILES_ENCRYPTION_SALT" }}
- name: CREDENTIALS_ENCRYPTION_KEY
  valueFrom:
    secretKeyRef:
      name: {{ include "co2-calculator.backendSecretName" . }}
      key: {{ .Values.backend.existingSecret.keys.credentialsEncryptionKeyKey | default "CREDENTIALS_ENCRYPTION_KEY" }}
- name: CREDENTIALS_ENCRYPTION_SALT
  valueFrom:
    secretKeyRef:
      name: {{ include "co2-calculator.backendSecretName" . }}
      key: {{ .Values.backend.existingSecret.keys.credentialsEncryptionSaltKey | default "CREDENTIALS_ENCRYPTION_SALT" }}
- name: FILES_MAX_SIZE_MB
  valueFrom:
    secretKeyRef:
      name: {{ include "co2-calculator.backendSecretName" . }}
      key: {{ .Values.backend.existingSecret.keys.filesMaxSizeMbKey | default "FILES_MAX_SIZE_MB" }}
- name: S3_ENDPOINT_PROTOCOL
  valueFrom:
    secretKeyRef:
      name: {{ include "co2-calculator.backendSecretName" . }}
      key: {{ .Values.backend.existingSecret.keys.s3EndpointProtocolKey | default "S3_ENDPOINT_PROTOCOL" }}
- name: S3_ENDPOINT_HOSTNAME
  valueFrom:
    secretKeyRef:
      name: {{ include "co2-calculator.backendSecretName" . }}
      key: {{ .Values.backend.existingSecret.keys.s3EndpointHostnameKey | default "S3_ENDPOINT_HOSTNAME" }}
- name: S3_ACCESS_KEY_ID
  valueFrom:
    secretKeyRef:
      name: {{ include "co2-calculator.backendSecretName" . }}
      key: {{ .Values.backend.existingSecret.keys.s3AccessKeyIdKey | default "S3_ACCESS_KEY_ID" }}
- name: S3_SECRET_ACCESS_KEY
  valueFrom:
    secretKeyRef:
      name: {{ include "co2-calculator.backendSecretName" . }}
      key: {{ .Values.backend.existingSecret.keys.s3SecretAccessKeyKey | default "S3_SECRET_ACCESS_KEY" }}
- name: S3_REGION
  valueFrom:
    secretKeyRef:
      name: {{ include "co2-calculator.backendSecretName" . }}
      key: {{ .Values.backend.existingSecret.keys.s3RegionKey | default "S3_REGION" }}
- name: S3_BUCKET
  valueFrom:
    secretKeyRef:
      name: {{ include "co2-calculator.backendSecretName" . }}
      key: {{ .Values.backend.existingSecret.keys.s3BucketKey | default "S3_BUCKET" }}
- name: S3_PATH_PREFIX
  valueFrom:
    secretKeyRef:
      name: {{ include "co2-calculator.backendSecretName" . }}
      key: {{ .Values.backend.existingSecret.keys.s3PathPrefixKey | default "S3_PATH_PREFIX" }}
# Elasticsearch audit export (OPDo), only when enabled (#500): a deployment
# without Elasticsearch needs none of its secret keys or CA file.
- name: ELASTICSEARCH_ENABLED
  value: {{ .Values.backend.elasticsearch.enabled | quote }}
{{- if .Values.backend.elasticsearch.enabled }}
- name: ELASTICSEARCH_HOSTS
  valueFrom:
    secretKeyRef:
      name: {{ include "co2-calculator.backendSecretName" . }}
      key: {{ .Values.backend.existingSecret.keys.elasticsearchHostsKey | default "ELASTICSEARCH_HOSTS" }}
- name: ELASTICSEARCH_INDEX
  valueFrom:
    secretKeyRef:
      name: {{ include "co2-calculator.backendSecretName" . }}
      key: {{ .Values.backend.existingSecret.keys.elasticsearchIndexKey | default "ELASTICSEARCH_INDEX" }}
- name: ELASTICSEARCH_ID
  valueFrom:
    secretKeyRef:
      name: {{ include "co2-calculator.backendSecretName" . }}
      key: {{ .Values.backend.existingSecret.keys.elasticsearchIdKey | default "ELASTICSEARCH_ID" }}
- name: ELASTICSEARCH_API_KEY
  valueFrom:
    secretKeyRef:
      name: {{ include "co2-calculator.backendSecretName" . }}
      key: {{ .Values.backend.existingSecret.keys.elasticsearchApiKeyKey | default "ELASTICSEARCH_API_KEY" }}

{{- end }}
# Tableau connection credentials are stored per-connector in the
# DB (ConnectorConnection, #1552) — entered via the API-connect
# form, not injected from the backend secret. Only operational
# knobs remain here.
- name: TABLEAU_MODULES
  value: {{ .Values.backend.tableau.modules | default "" | quote }}
- name: TABLEAU_VERIFY_SSL
  value: {{ .Values.backend.tableau.verifySsl | default "true" | quote }}
- name: TABLEAU_REQUEST_TIMEOUT_SECONDS
  value: {{ .Values.backend.tableau.requestTimeoutSeconds | default "" | quote }}
- name: TABLEAU_REST_MIN_API_VERSION
  value: {{ .Values.backend.tableau.restMinApiVersion | default "" | quote }}
- name: TABLEAU_MAX_FIELDS
  value: {{ .Values.backend.tableau.maxFields | default "" | quote }}

- name: CONNECTOR_ALLOWED_HOST_SUFFIXES
  value: {{ .Values.backend.connector.allowedHostSuffixes | default "" | quote }}

{{- if .Values.backend.elasticsearch.enabled }}
- name: ELASTICSEARCH_CA_CERT
  value: {{ .Values.backend.elasticsearch.caCert.path | default "/tmp/" }}{{ .Values.backend.elasticsearch.caCert.filename | default "http_ca_test.crt" }}
{{- end }}
- name: POD_NAME
  valueFrom:
    fieldRef:
      fieldPath: metadata.name
- name: POD_NAMESPACE
  valueFrom:
    fieldRef:
      fieldPath: metadata.namespace
# #2258 follow-up — routable pod IP, stored in the ``pods`` heartbeat
# table so a factor write can POST an internal cache-clear directly to
# every other live pod instead of relying solely on the 60s TTL.
- name: POD_IP
  valueFrom:
    fieldRef:
      fieldPath: status.podIP
- name: OTEL_RESOURCE_ATTRIBUTES
  value: k8s.pod.name=$(POD_NAME),k8s.namespace.name=$(POD_NAMESPACE)
{{ include "co2-calculator.backendObservabilityEnv" . }}
{{- end -}}

{{/*
Observability switches of the backend and the worker (#500), from
backend.observability. An enabled service without its endpoint fails the
render instead of exporting to a default address.
*/}}
{{- define "co2-calculator.backendObservabilityEnv" -}}
{{- $otel := .Values.backend.observability.otel -}}
{{- $loki := .Values.backend.observability.loki -}}
- name: OTEL_SDK_DISABLED
  value: {{ not $otel.enabled | quote }}
{{- if $otel.enabled }}
- name: OTEL_EXPORTER_OTLP_ENDPOINT
  value: {{ required "backend.observability.otel.endpoint is required when otel is enabled" $otel.endpoint | quote }}
- name: OTEL_EXPORTER_OTLP_PROTOCOL
  value: {{ $otel.protocol | quote }}
- name: OTEL_SERVICE_NAME
  value: {{ $otel.serviceName | quote }}
{{- end }}
- name: LOKI_ENABLED
  value: {{ $loki.enabled | quote }}
{{- if $loki.enabled }}
- name: LOKI_URL
  value: {{ required "backend.observability.loki.url is required when loki is enabled" $loki.url | quote }}
{{- with $loki.tenantId }}
- name: LOKI_TENANT_ID
  value: {{ . | quote }}
{{- end }}
{{- end }}
{{- end -}}

{{/*
Shared volume + volumeMount for the Elasticsearch CA cert every backend-
image pod needs (audit sync runs from the worker too). Plan #2050 Track B.
*/}}
{{- define "co2-calculator.backendSecretVolumeMount" -}}
{{- if .Values.backend.elasticsearch.enabled }}
- name: backend-secret
  mountPath: {{ .Values.backend.elasticsearch.caCert.path | default "/tmp/" }}{{ .Values.backend.elasticsearch.caCert.filename | default "http_ca_test.crt" }}
  subPath: {{ .Values.backend.elasticsearch.caCert.filename | default "http_ca_test.crt" }}
  readOnly: true
{{- end }}
{{- end -}}

{{- define "co2-calculator.backendSecretVolume" -}}
{{- if .Values.backend.elasticsearch.enabled }}
- name: backend-secret
  secret:
    secretName: {{ include "co2-calculator.backendSecretName" . }}
    items:
      - key: {{ .Values.backend.existingSecret.keys.elasticsearchCaCertFileKey | default "ELASTICSEARCH_CA_CERT_FILE" }}
        path: {{ .Values.backend.elasticsearch.caCert.filename | default "http_ca_test.crt" }}
{{- end }}
{{- end -}}
