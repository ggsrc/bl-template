# Try it locally: the platform and GitOps layers on your laptop

中文：[README_zh.md](./README_zh.md)

No GCP, no domain, no cost. Use a local Kubernetes cluster (kind, minikube or Docker Desktop) to try
**layer 3 (platform)** and **layer 4 (applications)** of the [0→1 guide](../../docs/GETTING_STARTED.md):

- Platform: External Secrets controller, Sealed Secrets, ArgoCD, VictoriaMetrics (storage and alerting), Grafana
- GitOps: put your app in a Git repository and let ArgoCD deploy it

Layers 1 and 2 (GCP projects, network, GKE, DNS, certificates) need a real cloud account and are skipped.
When you move to the cloud, it is the same components and the same blcli workflow.

Allow 20–40 minutes, mostly for pulling images.

## 0. Prerequisites

- Docker, plus [kind](https://kind.sigs.k8s.io/) or [minikube](https://minikube.sigs.k8s.io/)
- `kubectl`, `helm`, `kustomize`, `curl`, `git`, `ssh-keygen`, `blcli`
- A GitHub account
- At least 4 CPUs and 6 GB of **free** memory in Docker (Docker Desktop's memory is shared by all containers, so stop the ones you don't need; when memory runs out the API server stops responding and installs time out)

## 1. Create a local cluster

```bash
kind create cluster --name bl-local
# or: minikube start -p bl-local --cpus 4 --memory 5g
kubectl config current-context     # kind-bl-local or bl-local; every command below uses the current context
```

## 2. Create the gitops repository and render the configuration

1. Create an **empty repository** on GitHub (private is fine), e.g. `<you>/gitops`.
2. Copy the args file and replace both `git@github.com:example-org/gitops.git` with your repository:
   ```bash
   cp <bl-template>/examples/local/args.yaml ./args.yaml
   ```
3. Render the Kubernetes and GitOps configuration:
   ```bash
   blcli init <bl-template> -a args.yaml --modules kubernetes --modules gitops -o ./local-workspace
   ```
   `<bl-template>` is a local checkout of this repository or `github.com/ggsrc/bl-template`.

What you get:

| Directory | What it is |
|-----------|------------|
| `local-workspace/kubernetes/local/<component>/` | Install files for each platform component; the numeric prefix is the install order |
| `local-workspace/gitops/local/hello-world/` | The sample app's Deployment, Service, etc., and `app.yaml` for ArgoCD |
| `local-workspace/keys/argocd_github(.pub)` | The SSH key ArgoCD reads the repository with (never commit it) |

## 3. Add a read-only deploy key

```bash
cat local-workspace/keys/argocd_github.pub
```

Add it under the repository's **Settings → Deploy keys → Add deploy key**, with "Allow write access" unchecked.

## 4. Install the platform

```bash
blcli apply kubernetes -d ./local-workspace/kubernetes -r <bl-template>
```

Components install in `0-` → `2-` → `3-` → `4-` order.

**✅ Checkpoint**

```bash
kubectl get pods -A | grep -v kube-system      # all Running / Completed
kubectl -n monitoring-vm get vmsingle,vmagent,vmalert
```

## 5. Push the app to the gitops repository and hand it to ArgoCD

```bash
cd local-workspace/gitops
git init -b main && git add . && git commit -m "hello-world"
git remote add origin git@github.com:<you>/gitops.git && git push -u origin main
cd ../..
blcli apply gitops -d ./local-workspace/gitops --args args.yaml --skip-sync
```

This is GitOps: you only change Git, and ArgoCD keeps the cluster matching it.

**✅ Checkpoint**

```bash
kubectl -n argocd get applications              # hello-world becomes Synced + Healthy (a minute or two)
kubectl -n app port-forward svc/hello-world 8081:8080 &
curl localhost:8081                             # Hello from hello-world
```

## 6. Look around

| UI | How to open | Login |
|----|-------------|-------|
| ArgoCD | `kubectl -n argocd port-forward svc/argocd-server 8080:443`, open https://localhost:8080 | user `admin`, password: `kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath='{.data.password}' \| base64 -d` |
| Grafana | `kubectl -n grafana port-forward svc/grafana 3000:80`, open http://localhost:3000 | user `admin`, password: `kubectl -n grafana get secret grafana -o jsonpath='{.data.admin-password}' \| base64 -d` |
| VictoriaMetrics | `kubectl -n monitoring-vm port-forward svc/vmsingle-victoriametrics-vmks 8429`, open http://localhost:8429/vmui | none |

## 7. Change something

- **Release:** edit `-text=...` in `gitops/local/hello-world/deployment.yaml`, commit and push. ArgoCD syncs within a few minutes (or press Sync in the UI); `curl` shows the new text.
- **Roll back:** `git revert HEAD && git push`.
- **Metrics:** in Grafana Explore, pick the `victoria-metrics` datasource and query `up` or `container_memory_working_set_bytes`.

## Common issues

| Symptom | Cause and fix |
|---------|---------------|
| `open .../helm/repository/<some-repo>-index.yaml: no such file or directory` | The install scripts' `helm dependency update` refreshes every Helm repository on your machine, and an unrelated one has a broken cache. Run `helm repo update`, or `helm repo remove <name>`, then repeat step 4 |
| One component fails and later ones report `no matches for kind ...` / `ensure CRDs are installed first` | Later components need CRDs from earlier ones. Fix the first failure and repeat step 4; re-applying components that are already installed is fine |
| Install fails with `context deadline exceeded` / `TLS handshake timeout` | Usually out of memory, with the API server stalled. Check `docker stats` for other containers using memory, free some, and repeat step 4 |
| Pods stay `ContainerCreating` / `Pending` | First image pulls are slow; watch with `kubectl get pods -A -w`. For `Pending`, `kubectl describe pod` usually shows insufficient memory: give Docker / minikube more |
| The Application shows an authentication error | The deploy key is missing or on another repository; both repository URLs in `args.yaml` must match the real repository |

## 8. Clean up

```bash
kind delete cluster --name bl-local     # or: minikube delete -p bl-local
```

Delete the gitops repository and its deploy key on GitHub yourself.

## Local vs. cloud

| | Local | GCP ([0→1 guide](../../docs/GETTING_STARTED.md)) |
|---|---|---|
| Layers 1 and 2 | Skipped | Terraform creates projects, network, GKE, DNS, certificates |
| Secrets | External Secrets controller only, no secret store to read | Also `external-secrets`, reading GCP Secret Manager through Workload Identity |
| Alerts | Rules evaluated, nothing sent | Sent to Slack once the webhook is in Secret Manager |
| Sizing | 5Gi storage, 7-day retention | 20Gi storage, 30-day retention |
