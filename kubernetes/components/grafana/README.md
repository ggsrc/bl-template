# Grafana

## Prerequisites

- **helm** and **kubectl** must be in PATH. The install script checks for them before running.
- Optional: set `minHelmVersion` / `minKubectlVersion` in component args to enforce minimum versions.

## Install

渲染后执行（需先 `blcli init` 生成 values-corp.yaml）：

```bash
bash install
```

安装时使用 `values.yaml values-corp.yaml`；`values-corp.yaml.tmpl` 由 blcli 渲染，参数见 args.yaml（imageTag、rootUrl、vmDatasourceUrl、lokiDatasourceUrl、hostedDomain 等）。

Or manually:

```
helm dependency update
helm install grafana -n grafana . --values ./values.yaml --values ./values-corp.yaml
helm upgrade grafana -n grafana . --values ./values.yaml --values ./values-corp.yaml
```

若未使用 blcli 渲染，需自行从 values-corp.yaml.tmpl 复制并修改生成 values-corp.yaml。
