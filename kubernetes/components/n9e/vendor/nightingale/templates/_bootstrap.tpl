{{/* Generated credentials are cached across all templates in this render. */}}
{{- define "n9e.bootstrap" -}}
{{- if not (hasKey .Values "_bootstrap") -}}
  {{- $name := printf "%s-bootstrap" .Release.Name -}}
  {{- $secret := lookup "v1" "Secret" .Release.Namespace $name -}}
  {{- $data := dict -}}
  {{- if $secret -}}
    {{- range $key := list "admin-password" "mysql-password" "mysql-root-password" "redis-password" -}}
      {{- $_ := set $data $key (required (printf "bootstrap Secret is missing %s" $key) (index $secret.data $key) | b64dec) -}}
    {{- end -}}
  {{- else -}}
    {{- if .Release.IsUpgrade -}}{{ fail "bootstrap Secret missing on upgrade: complete the documented credential/data migration first" }}{{- end -}}
    {{- range $key := list "admin-password" "mysql-password" "mysql-root-password" "redis-password" -}}
      {{- if eq $key "admin-password" -}}
        {{/* Nightingale InitRoot only hashes seed passwords shorter than 32 chars. */}}
        {{- $_ := set $data $key (randAlphaNum 24) -}}
      {{- else -}}
        {{- $_ := set $data $key (randAlphaNum 48) -}}
      {{- end -}}
    {{- end -}}
  {{- end -}}
  {{- $_ := set .Values "_bootstrap" $data -}}
{{- end -}}
{{- range $key, $value := .Values._bootstrap -}}
  {{- $pattern := "^[A-Za-z0-9]{32,}$" -}}
  {{- if eq $key "admin-password" -}}{{- $pattern = "^[A-Za-z0-9]{24,31}$" -}}{{- end -}}
  {{- if not (regexMatch $pattern $value) -}}
    {{- fail (printf "bootstrap key %s has an invalid random password format (admin: 24-31 alphanumeric; DB/Redis: >=32)" $key) -}}
  {{- end -}}
{{- end -}}
{{- toJson .Values._bootstrap -}}
{{- end -}}
