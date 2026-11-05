# Security changes

Default changes that affect existing installations, why they were made, and what an existing install must do.
Re-render with `blcli init` and review the diff before applying anything.

## Ingress, ArgoCD and monitoring

- **web-ide removed.** The optional `web-ide` component (code-server behind oauth2-proxy) is gone: code-server ran with `--auth none` and any pod in the cluster could reach it without passing the proxy. Existing installs keep running until you remove them: `helm uninstall web-ide -n webide`, back up and delete its PVC, then rotate every credential that was stored in the IDE home volume and the oauth2-proxy client and cookie secrets.
- **ArgoCD deploy key kept out of git.** `kubernetes/init.sh` now writes the key pair to `<workspace>/keys` (or `BLCLI_KEYS_DIR`) instead of `<workspace>/kubernetes/keys`, writes `.gitignore` files for key material, and `gen_ssh_sealed_secrets.sh` pipes the Secret into kubeseal instead of writing `/tmp/ssh-secret.yaml`; the argocd `install` no longer writes `/tmp/argocd-manifests.yaml`. If `git log --all -- keys/` in your kubernetes repository finds the key, treat it as leaked: delete that deploy key on GitHub, generate a new one, add it as a read-only deploy key, re-run `gen_ssh_sealed_secrets.sh` and the argocd install, then run `git rm -r --cached keys/` and purge the history (for example `git filter-repo --path keys --invert-paths` plus a force-push). Also delete any leftover `/tmp/ssh-secret.yaml` and `/tmp/argocd-manifests.yaml`.
