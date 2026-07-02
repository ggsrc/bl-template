# Redis

基于 Bitnami Redis Helm Chart 的共享 Redis 部署，参考 `alva-infra/gitops/alva-ai-infra/components-stg/2-redis/`。

## 特性

- standalone 模式，AOF 持久化
- 通过 ExternalSecret 注入密码（`auth.existingSecret`）
- 可选 GCP Internal LoadBalancer（`enable-internal-lb`）

## 安装

```bash
bash ./install
```

## 前置条件

- 在 GCP Secret Manager 中存储 Redis 密码
- 通过 `external-secrets` 组件同步为 `redis-shared` Secret（键名 `REDIS_PASSWORD`）
