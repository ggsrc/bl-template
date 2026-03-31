# Victoria Metrics K8s Stack

## Prerequisites

- **helm** and **kubectl** must be in PATH. The install script checks for them before running.
- Optional: set `minHelmVersion` / `minKubectlVersion` in component args to enforce minimum versions.

## Install

渲染后执行（需先 `blcli init` 生成 values-override.yaml）：

```bash
bash install
```

安装时使用 `values.yaml values-override.yaml`；`values-override.yaml.tmpl` 由 blcli 渲染，参数见 args.yaml（cluster、env、remoteWriteUrl、vmagent 资源等）。

Install dependencies:
```
# https://artifacthub.io/packages/helm/prometheus-community/prometheus-operator-crds
helm install prometheus-operator-crds oci://ghcr.io/prometheus-community/charts/prometheus-operator-crds
```

## Alva

```
# corp env
helm upgrade -i -n monitoring-vm victoriametrics . --values values.yaml --values values-corp.yaml

# stg env
helm upgrade -i -n monitoring-vm victoriametrics . --values values.yaml --values values-stg.yaml

# prd env
helm upgrade -i -n monitoring-vm victoriametrics . --values values.yaml --values values-prd.yaml

```


## API - cluster version

- Datasource: `http://vmselect-victoriametrics-vmks:8481/select/0/prometheus`
- VM Web UI: `http://vmselect-victoriametrics-vmks:8481/select/0/vmui` 
- query api:
  - inCluster: `http://vmselect-victoriametrics-vmks.monitoring-vm.svc.cluster.local:8481/select/0/prometheus`
- remoteWrite:
  - format: `http://<vminsert-host>:8480/insert/<accountID>/prometheus/api/v1/write`
  - inCluster: `http://vminsert-victoriametrics-vmks:8480/insert/0/prometheus/api/v1/write`
- VM Agent UI: `http://vmagent-victoriametrics-vmks:8429`
  - shows the active targets, discovered targets, etc
  - inCluster: `http://vminsert-victoriametrics-vmks/insert/0/prometheus/api/v1/write`

Access via port-forward:

```bash
# check vmagent's targets status
kubectl port-forward -n monitoring-vm service/vmagent-victoriametrics-vmks 8429

# access vmselect's web ui
kubectl port-forward -n monitoring-vm service/vmselect-victoriametrics-vmks 8481
```
