{{/*
Expand the name of the chart.
*/}}
{{- define "agency-backend.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "agency-backend.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "agency-backend.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "agency-backend.labels" -}}
helm.sh/chart: {{ include "agency-backend.chart" . }}
{{ include "agency-backend.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "agency-backend.selectorLabels" -}}
app.kubernetes.io/name: {{ include "agency-backend.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "agency-backend.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "agency-backend.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Database URL
*/}}
{{- define "agency-backend.databaseUrl" -}}
{{- if .Values.postgresql.enabled }}
{{- printf "postgresql://%s:%s@%s-postgresql:5432/%s" .Values.postgresql.auth.username .Values.postgresql.auth.password (include "agency-backend.fullname" .) .Values.postgresql.auth.database }}
{{- else }}
{{- .Values.secrets.DATABASE_URL }}
{{- end }}
{{- end }}

{{/*
Redis URL
*/}}
{{- define "agency-backend.redisUrl" -}}
{{- if .Values.redis.enabled }}
{{- if .Values.redis.auth.enabled }}
{{- printf "redis://:%s@%s-redis-master:6379/0" .Values.redis.auth.password (include "agency-backend.fullname" .) }}
{{- else }}
{{- printf "redis://%s-redis-master:6379/0" (include "agency-backend.fullname" .) }}
{{- end }}
{{- else }}
{{- .Values.secrets.REDIS_URL }}
{{- end }}
{{- end }}