# Victoria Metrics Alert Rules

Alert rules, VMAgent config, and related resources for Victoria Metrics (applied via Kustomize).

## Prerequisites

- **kubectl** must be in PATH. The install script uses `kubectl kustomize` (built-in). It checks kubectl before running.
- Optional: set `minKubectlVersion` in component args to enforce a minimum version.

## Install

渲染后执行（需先 `blcli init` 生成 vmalertmanagerconfig.yaml 等）：

```bash
bash install
```

`vmalertmanagerconfig.yaml.tmpl` 由 blcli 渲染，参数见 args.yaml（namespace、alertCluster、slackChannel 等）。

Or manually:

```bash
kubectl kustomize . | kubectl apply -f -
```

Ensure the Victoria Metrics operator and CRDs are installed first (see victoria-metrics-operator).
