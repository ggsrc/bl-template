# Victoria Metrics Alert Rules

Alert rules, VMAgent config, and related resources for Victoria Metrics (applied via Kustomize).

## Prerequisites

- **kubectl** must be in PATH. The install script uses `kubectl kustomize` (built-in). It checks kubectl before running.
- Optional: set `minKubectlVersion` in component args to enforce a minimum version.

## Install

After rendering (run `blcli init` first to generate vmalertmanagerconfig.yaml and related files), run:

```bash
bash install
```

`vmalertmanagerconfig.yaml.tmpl` is rendered by blcli, with parameters in args.yaml (namespace, alertCluster, slackChannel, etc.).

Or manually:

```bash
kubectl kustomize . | kubectl apply -f -
```

Ensure the Victoria Metrics operator and CRDs are installed first (see victoria-metrics-operator).
