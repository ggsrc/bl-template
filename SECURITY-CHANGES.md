# Security changes

Default changes that affect existing installations, why they were made, and what an existing install must do.
Re-render with `blcli init` and review the diff before applying anything.

## Ingress, ArgoCD and monitoring

- **web-ide removed.** The optional `web-ide` component (code-server behind oauth2-proxy) is gone: code-server ran with `--auth none` and any pod in the cluster could reach it without passing the proxy. Existing installs keep running until you remove them: `helm uninstall web-ide -n webide`, back up and delete its PVC, then rotate every credential that was stored in the IDE home volume and the oauth2-proxy client and cookie secrets.
