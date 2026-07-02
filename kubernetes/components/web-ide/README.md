# Web-IDE Helm Chart

这是一个基于 [coder/code-server](https://github.com/coder/code-server) 的 Helm chart，支持通过 oauth2-proxy 实现 OAuth 认证。

## 功能特性

- 支持 OAuth 认证（Google OAuth 2.0）
- 持久化存储
- Istio 集成
- 资源限制和请求配置
- 可扩展的配置选项

## 前置要求

1. Kubernetes 1.19+
2. Helm 3.0+
3. Istio（如果使用 Istio ingress）
4. Google OAuth 应用配置（Client ID 和 Client Secret）

## 前置准备

### 1. 配置 Google OAuth

在部署之前，需要配置 Google OAuth 应用：

1. 访问 [Google Cloud Console](https://console.cloud.google.com/)
2. 创建 OAuth 2.0 客户端 ID
3. 设置授权重定向 URI: `https://web-ide.stg.alva.xyz/oauth2/callback`
4. 获取 Client ID 和 Client Secret

### 2. 创建 OAuth Secret

1. 在 gcp console 上的 secret manager 存储对应的 oauth client secret，格式如下
```json
{
  "google-client-secret": "{secret}"
}
```
2. 通过 externalSecret 创建对应的 secret

## 安装

### 使用 Helm 安装

```bash
# 安装 chart（使用默认配置）
helm install web-ide . --namespace=webide

# 使用自定义 values 文件
helm install web-ide . \
  --namespace=webide \
  --values values.yaml \
  --values values-stg.yaml

# 生产环境部署
helm install web-ide . \
  --namespace=webide \
  --values values.yaml \
  --values values-prd.yaml
```

## 配置说明

### 主要配置选项

- `oauth2Proxy.enabled`: 启用 OAuth2 代理
- `oauth2Proxy.provider`: OAuth 提供商（google）
- `oauth2Proxy.secretName`: OAuth 凭据 secret 名称
- `oauth2Proxy.clientSecretKey`: secret 中的客户端密钥键名

### 资源配置

- `resources.limits`: 资源限制
- `resources.requests`: 资源请求
- `persistence.size`: 持久化存储大小

### Ingress 配置

- `ingress.enabled`: 启用 Ingress
- `ingress.annotations`: Ingress 注解（支持 Istio）
- `ingress.hosts`: 域名配置

## 升级

```bash
# 升级到新版本
helm upgrade web-ide . \
  --namespace=webide \
  --values values.yaml \
  --values values-stg.yaml

# 生产环境升级
helm upgrade web-ide . \
  --namespace=webide \
  --values values.yaml \
  --values values-prd.yaml
```

## 卸载

```bash
# 卸载 chart
helm uninstall web-ide -n webide

# 清理相关资源（可选）
kubectl delete secret web-ide-secrets -n webide
```

## 故障排除

### 常见问题

1. **OAuth 认证失败**
   - 检查 `web-ide-secrets` secret 是否存在
   - 确认 secret 中包含 `google-client-secret` 键
   - 检查 Client Secret 是否正确
   - 确认回调 URL 配置正确

2. **Pod 启动失败**
   - 检查资源配额
   - 查看 Pod 日志：`kubectl logs -n webide deployment/web-ide`

3. **存储问题**
   - 检查 StorageClass 是否可用
   - 确认有足够的存储空间

### 查看状态

```bash
# 查看 Pod 状态
kubectl get pods -n webide -l app=web-ide

# 查看服务状态
kubectl get svc -n webide -l app=web-ide

# 查看 Ingress 状态
kubectl get ingress -n webide -l app=web-ide

# 查看日志
kubectl logs -n webide deployment/web-ide

# 检查 secret
kubectl describe secret web-ide-secrets -n webide
```

## 参考

- [Code-Server 官方文档](https://coder.com/docs/code-server)
- [Code-Server GitHub](https://github.com/coder/coder/code-server)
- [Helm 官方文档](https://helm.sh/docs/)
- [OAuth2 Proxy 文档](https://oauth2-proxy.github.io/oauth2-proxy/)
