# Kubernetes 可选组件

以下组件已在 `kubernetes/config.yaml` 注册，**默认不在** `kubernetes/default.yaml` 中启用。需要在生成的 `args.yaml` 里向 `kubernetes.projects[].components[]` 手动添加对应条目后，`blcli init` 才会渲染。

所有镜像均使用**上游官方镜像**（非 Alva 私有 registry）。

## 启用方式

```yaml
kubernetes:
  projects:
    - name: stg
      components:
        - name: cnpg
          parameters:
            namespace: cnpg
            release-name: cloudnative-pg
        - name: redis
          parameters:
            namespace: redis
            existing-secret: redis-shared
```

安装：在渲染输出目录执行 `bash ./install`（Helm 组件）或 `kubectl apply -k .`（Kustomize 组件）。

## 组件列表

| 组件 | 官方镜像 / Chart | 依赖 | 说明 |
|------|------------------|------|------|
| cnpg | `ghcr.io/cloudnative-pg/cloudnative-pg` | — | CloudNativePG Operator |
| redis | Bitnami Chart → `bitnami/redis` | external-secrets | 共享 Redis |
| paradedb | ParadeDB 官方 Chart | cnpg | PostgreSQL + 搜索扩展 |
| kafka | Bitnami Chart → `bitnami/kafka` | — | KRaft 模式 Kafka |
| juicefs | `juicedata/mount` | external-secrets | JuiceFS S3 Gateway（Kustomize） |
| loki | Grafana Community Chart | — | 日志聚合 |
| grafana | `grafana/grafana` | victoria-metrics-operator | **默认栈 corp 已含**；也可单独 opt-in |
| otel-collector | OpenTelemetry 官方 Chart | — | 日志/指标/链路采集 |
| uptrace | `uptrace/uptrace` | cnpg | APM（官方 Helm） |
| n9e | `flashcatcloud/nightingale` | victoria-metrics-operator | 夜莺监控 |
| bytebase | `bytebase/bytebase` | — | 数据库变更管理 |
| web-ide | `codercom/code-server` | external-secrets, istio | 浏览器 IDE（**仅 bl-template**） |
| navigation | `b4bz/homer` | — | 内部导航页（Homer，**仅 bl-template**） |

## 依赖顺序

blcli 会按 `config.yaml` 中的 `dependencies` 自动排序，例如：

- `cnpg` ← paradedb、uptrace
- `external-secrets` ← redis、juicefs、web-ide
- `victoria-metrics-operator` ← grafana、n9e

## 与 default.yaml 的关系

| 来源 | 含义 |
|------|------|
| `config.yaml` | 模板仓库**能**提供的全部组件 |
| `default.yaml` | `init-args` 默认写入 args 的核心栈（ESO、Istio、ArgoCD、VM 等） |
| 本文件所列组件 | 需用户在 args 中 **opt-in** |

各组件参数见 `kubernetes/components/<name>/args.yaml`，或运行 `blcli explain -r <repo> -m kubernetes -c <name>`。
