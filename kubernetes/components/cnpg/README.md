# CloudNativePG Operator

CloudNativePG 是用于在 Kubernetes 上运行 PostgreSQL 集群的 Operator。

参考：`alva-infra/k8s/common/cloudnative-pg/`

## 安装

由 blcli 渲染后，在组件目录执行：

```bash
bash ./install
```

或手动：

```bash
helm dependency update
helm upgrade --install cloudnative-pg . -n cnpg --create-namespace \
  -f values.yaml -f values-override.yaml --wait
```

## 创建 PostgreSQL 集群

安装 Operator 后，通过 `postgresql.cnpg.io/v1` `Cluster` CR 创建数据库集群。集群定义通常放在 GitOps 仓库中（参考 `alva-infra/gitops/alva-ai-infra/components-*/1-db/`）。
