{{- define version-sync.name -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix - -}}
{{- end -}}

{{- define version-sync.fullname -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix - -}}
{{- else -}}
{{-  := default .Chart.Name .Values.nameOverride -}}
{{- if contains  .Release.Name -}}
{{- .Release.Name | trunc 63 | trimSuffix - -}}
{{- else -}}
{{- printf %s-%s .Release.Name  | trunc 63 | trimSuffix - -}}
{{- end -}}
{{- end -}}
{{- end -}}

{{- define version-sync.labels -}}
app.kubernetes.io/name: {{ include version-sync.name . }}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version | replace + _ }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end -}}
