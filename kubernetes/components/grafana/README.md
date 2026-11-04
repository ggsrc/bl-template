# Grafana

## Prerequisites

- **helm** and **kubectl** must be in PATH. The install script checks for them before running.
- Optional: set `minHelmVersion` / `minKubectlVersion` in component args to enforce minimum versions.

## Install

After rendering (run `blcli init` first to generate values-corp.yaml), run:

```bash
bash install
```

The install uses `values.yaml values-corp.yaml`; `values-corp.yaml.tmpl` is rendered by blcli, with parameters in args.yaml (imageTag, rootUrl, vmDatasourceUrl, lokiDatasourceUrl, hostedDomain, etc.).

Or manually:

```
helm dependency update
helm install grafana -n grafana . --values ./values.yaml --values ./values-corp.yaml
helm upgrade grafana -n grafana . --values ./values.yaml --values ./values-corp.yaml
```

If you do not render with blcli, create values-corp.yaml yourself by copying and editing values-corp.yaml.tmpl.
