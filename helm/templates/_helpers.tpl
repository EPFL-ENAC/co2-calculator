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

{{- define "co2-calculator.backendSecretName" -}}
{{- if and .Values.backend.externalSecret.enabled .Values.backend.externalSecret.name -}}
{{- .Values.backend.externalSecret.name -}}
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
Database URL construction
*/}}
{{- define "co2-calculator.databaseUrl" -}}
{{- if .Values.database.external.enabled -}}
  {{- if .Values.database.external.url -}}
    {{- .Values.database.external.url -}}
  {{- else -}}
    {{- printf "postgresql://%s:%s@%s:%d/%s" .Values.database.external.username .Values.database.external.password .Values.database.external.host (.Values.database.external.port | int) .Values.database.external.database -}}
  {{- end -}}
{{- else if .Values.database.local.enabled -}}
  {{- printf "sqlite+aiosqlite:///%s" .Values.database.local.path -}}
{{- end -}}
{{- end -}}

{{/*
Database volume definition
*/}}
{{- define "co2-calculator.databaseVolume" -}}
{{- if .Values.database.local.enabled -}}
- name: sqlite-data
  {{- if and .Values.database.local.storage.persistentVolumeClaim.enabled (eq .Values.database.local.storage.type "persistentVolumeClaim") }}
  persistentVolumeClaim:
    claimName: {{ include "co2-calculator.fullname" . }}-sqlite
  {{- else }}
  emptyDir:
    {{- with .Values.database.local.storage.emptyDir.sizeLimit }}
    sizeLimit: {{ . }}
    {{- end }}
  {{- end }}
{{- end -}}
{{- end -}}

{{/*
Database volume mount
*/}}
{{- define "co2-calculator.databaseVolumeMount" -}}
{{- if .Values.database.local.enabled -}}
- name: sqlite-data
  mountPath: /data
{{- end -}}
{{- end -}}