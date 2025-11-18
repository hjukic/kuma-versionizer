{{- define kuma-versionizer.name -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix - -}}
{{- end -}}

{{- define kuma-versionizer.fullname -}}
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

{{- define kuma-versionizer.labels -}}
app.kubernetes.io/name: {{ include kuma-versionizer.name . }}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version | replace + _ }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end -}}
