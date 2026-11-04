# Web-IDE Helm Chart

A Helm chart based on [coder/code-server](https://github.com/coder/code-server), with OAuth authentication through oauth2-proxy.

## Features

- OAuth authentication (Google OAuth 2.0)
- Persistent storage
- Istio integration
- Configurable resource limits and requests
- Extensible configuration options

## Requirements

1. Kubernetes 1.19+
2. Helm 3.0+
3. Istio (if you use the Istio ingress)
4. A Google OAuth application (Client ID and Client Secret)

## Preparation

### 1. Configure Google OAuth

Before deploying, configure a Google OAuth application:

1. Open the [Google Cloud Console](https://console.cloud.google.com/)
2. Create an OAuth 2.0 client ID
3. Set the authorized redirect URI: `https://web-ide.stg.example.com/oauth2/callback`
4. Copy the Client ID and Client Secret

### 2. Create the OAuth secret

1. Store the OAuth client secret in Secret Manager in the GCP console, in this format:
```json
{
  "google-client-secret": "{secret}"
}
```
2. Create the matching Kubernetes secret with an ExternalSecret

## Install

### Install with Helm

```bash
# Install the chart (default configuration)
helm install web-ide . --namespace=webide

# Use custom values files
helm install web-ide . \
  --namespace=webide \
  --values values.yaml \
  --values values-stg.yaml

# Production deployment
helm install web-ide . \
  --namespace=webide \
  --values values.yaml \
  --values values-prd.yaml
```

## Configuration

### Main options

- `oauth2Proxy.enabled`: enable the OAuth2 proxy
- `oauth2Proxy.provider`: OAuth provider (google)
- `oauth2Proxy.secretName`: name of the secret holding the OAuth credentials
- `oauth2Proxy.clientSecretKey`: key of the client secret inside that secret

### Resources

- `resources.limits`: resource limits
- `resources.requests`: resource requests
- `persistence.size`: persistent volume size

### Ingress

- `ingress.enabled`: enable Ingress
- `ingress.annotations`: Ingress annotations (Istio supported)
- `ingress.hosts`: host names

## Upgrade

```bash
# Upgrade to a new version
helm upgrade web-ide . \
  --namespace=webide \
  --values values.yaml \
  --values values-stg.yaml

# Production upgrade
helm upgrade web-ide . \
  --namespace=webide \
  --values values.yaml \
  --values values-prd.yaml
```

## Uninstall

```bash
# Uninstall the chart
helm uninstall web-ide -n webide

# Clean up related resources (optional)
kubectl delete secret web-ide-secrets -n webide
```

## Troubleshooting

### Common issues

1. **OAuth authentication fails**
   - Check that the `web-ide-secrets` secret exists
   - Confirm that the secret contains the `google-client-secret` key
   - Check that the Client Secret is correct
   - Confirm that the callback URL is configured correctly

2. **Pod fails to start**
   - Check resource quotas
   - Check the Pod logs: `kubectl logs -n webide deployment/web-ide`

3. **Storage issues**
   - Check that the StorageClass is available
   - Confirm there is enough storage space

### Check status

```bash
# Pod status
kubectl get pods -n webide -l app=web-ide

# Service status
kubectl get svc -n webide -l app=web-ide

# Ingress status
kubectl get ingress -n webide -l app=web-ide

# Logs
kubectl logs -n webide deployment/web-ide

# Inspect the secret
kubectl describe secret web-ide-secrets -n webide
```

## References

- [Code-Server documentation](https://coder.com/docs/code-server)
- [Code-Server GitHub](https://github.com/coder/coder/code-server)
- [Helm documentation](https://helm.sh/docs/)
- [OAuth2 Proxy documentation](https://oauth2-proxy.github.io/oauth2-proxy/)
