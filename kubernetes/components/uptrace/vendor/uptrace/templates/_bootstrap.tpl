{{/* Generated credentials are cached across all templates in this render. */}}
{{- define "uptrace.bootstrap" -}}
{{- if not (hasKey .Values "_bootstrap") -}}
  {{- $name := printf "%s-bootstrap" .Release.Name -}}
  {{- $secret := lookup "v1" "Secret" .Release.Namespace $name -}}
  {{- $data := dict -}}
  {{- if $secret -}}
    {{- range $key := list "admin-password" "service-secret" "user-token" "project-token" "clickhouse-password" -}}
      {{- $_ := set $data $key (required (printf "bootstrap Secret is missing %s" $key) (index $secret.data $key) | b64dec) -}}
    {{- end -}}
  {{- else -}}
    {{- if .Release.IsUpgrade -}}{{ fail "bootstrap Secret missing on upgrade: complete the documented credential/data migration first" }}{{- end -}}
    {{- range $key := list "admin-password" "service-secret" "user-token" "project-token" "clickhouse-password" -}}
      {{- $_ := set $data $key (randAlphaNum 48) -}}
    {{- end -}}
  {{- end -}}
  {{- $_ := set .Values "_bootstrap" $data -}}
{{- end -}}
{{- range $key, $value := .Values._bootstrap -}}
  {{- if not (regexMatch "^[A-Za-z0-9]{32,}$" $value) -}}
    {{- fail (printf "bootstrap key %s must contain at least 32 random alphanumeric characters" $key) -}}
  {{- end -}}
{{- end -}}
{{- toJson .Values._bootstrap -}}
{{- end -}}
