{{- define "launcher.name" -}}launcher{{- end -}}

{{- define "launcher.labels" -}}
app.kubernetes.io/name: {{ include "launcher.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version }}
{{- end -}}

{{- define "launcher.selectorLabels" -}}
app.kubernetes.io/name: {{ include "launcher.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{- define "launcher.databaseUrl" -}}
{{- if .Values.postgres.enabled -}}
postgresql+asyncpg://{{ .Values.postgres.user }}:{{ .Values.postgres.password }}@launcher-postgres:5432/{{ .Values.postgres.database }}
{{- else -}}
sqlite+aiosqlite:////tmp/launcher.db
{{- end -}}
{{- end -}}

{{- define "launcher.egressAllowlist" -}}
{{- join "," .Values.egress.allowlist -}}
{{- end -}}
