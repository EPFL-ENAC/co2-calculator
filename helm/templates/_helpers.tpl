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
{{- if and .Values.backend.existingSecret.enabled .Values.backend.existingSecret.name -}}
{{- .Values.backend.existingSecret.name -}}
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
