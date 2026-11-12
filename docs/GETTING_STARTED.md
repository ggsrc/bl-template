# Build Your Infra from 0 to 1

中文版：[GETTING_STARTED_zh.md](./GETTING_STARTED_zh.md)

This guide is for **startups and individual developers**: you probably don't have a dedicated SRE, but you want infrastructure that can grow with you from day one. Beyond which command to run, it explains **what each layer is, why you need it, and which directory in this template implements it** — so you understand your own infra instead of inheriting a pile of YAML.

---

## The big picture: four layers

```
┌───────────────────────────────────────────────────────────────┐
│ Layer 4  Applications      gitops/             ArgoCD Applications │
├───────────────────────────────────────────────────────────────┤
│ Layer 3  Platform          kubernetes/   secrets / ingress / GitOps / monitoring │
├───────────────────────────────────────────────────────────────┤
│ Layer 2  Environment       terraform/project/  VPC / GKE / DNS / certs │
├───────────────────────────────────────────────────────────────┤
│ Layer 1  Cloud foundation  terraform/init/     state store / GCP projects │
└───────────────────────────────────────────────────────────────┘
          blcli: init-args → init → apply → status → rollback
```

Each layer depends on the one below it, so you always build **bottom-up**. blcli enforces the order from the `dependencies` declared in each `config.yaml`.

| Layer | Problem it solves | Without it |
|-------|-------------------|------------|
| Cloud foundation | Ownership, billing, where Terraform state lives | People overwrite each other's changes; resources scatter |
| Environment | Network, cluster, domains, certificates | Console click-ops that nobody can reproduce or audit |
| Platform | Secrets, ingress, delivery, observability | Every service reinvents them; incidents are invisible |
| Applications | Declarative deployment | Hand-typed `kubectl apply`; rollback from memory |

---

## Stage 0: Prerequisites

**You need:**

- A GCP account and Billing Account (a GCP Organization is **not** required — set `OrganizationID` to `"0"`, see [terraform/TERRAFORM_PROJECT.md](../terraform/TERRAFORM_PROJECT.md))
- A domain (can come later, but certificates and public access depend on it)
- A GitHub org or account to hold the generated terraform / kubernetes / gitops repos
- Local tools: `blcli`, `terraform`, `gcloud`, `kubectl`, `helm`, `gh`, plus `kustomize` and `curl` for the ArgoCD install script
- `gcloud auth login` and `gcloud auth application-default login` (Terraform uses the latter)

**Have these ready before you start, and fill them into the argocd parameters in `args.yaml`:**

| What | Used by | Without it |
|------|---------|------------|
| A GitHub App (App ID, Installation ID and private key `.pem`) installed on the org that holds the gitops repo | ArgoCD pulling the private gitops repo | ArgoCD install stops with `set GitHubAppID and GitHubAppInstallationID` |
| A GitHub OAuth App (Client ID and Client Secret) and the GitHub org allowed to sign in | ArgoCD GitHub login (Dex) | The defaults are placeholders (`clientID: XXXXXXX`, `example-org`): it installs but nobody can log in; removing the org restriction makes install stop with `The Dex GitHub connector has no orgs` |
| `slack-webhook-url-infra-alert` in Secret Manager (a Slack Incoming Webhook URL) | Alerts to Slack | Rules are still evaluated, but Alertmanager has no webhook and cannot send alerts |

**Generate your parameter file:**

```bash
blcli init-args -r github.com/ggsrc/bl-template -o args.yaml
```

`args.yaml` is the single source of truth for your whole infra. Every parameter is described with an example in the template's `args.yaml` files; use `blcli explain` (e.g. `blcli explain -r github.com/ggsrc/bl-template -m kubernetes -c argocd`) when one is unclear. Design details: [ARGS_DESIGN.md](../ARGS_DESIGN.md).

> **One environment by default.** The template generates a single `prd` project: one GCP project, one GKE cluster, one platform stack, with monitoring self-contained in that cluster. When your team needs `stg` / `prd` / a shared `corp`, follow [examples/multi-env/](../examples/multi-env/) and add environments the same way. That is the point of templating.

---

## Stage 1: Cloud foundation (`terraform/init/`)

**What:** Before any workload resources, settle two things — where Terraform state lives and which GCP project owns each resource.

| Generated directory | Purpose |
|---------------------|---------|
| `terraform/init/0-terraform-statestore/` | GCS bucket for Terraform state (`prepare: true`, runs first) |
| `terraform/init/1-<GlobalName>-projects/` | GCP projects and required APIs |
| `terraform/init/2-atlantis/` | (Optional) Atlantis service account for PR-driven Terraform |

**Why:** Remote state keeps collaborators from overwriting each other; one GCP project per environment isolates permissions, billing, and failures.

**Small-team tip:** Atlantis can wait. With one or two people on infra, local `terraform apply` plus code review is enough.

**✅ Checkpoint**

```bash
gcloud projects list                   # shows <GlobalName>-tfstore-xxxx and <GlobalName>-prd-xxxx
gcloud storage ls --project <GlobalName>-tfstore-xxxx   # shows the state bucket
# in terraform/init/1-<GlobalName>-projects/:
terraform output project_ids           # the real project ID behind prd, used in later stages
```

Project IDs get a random suffix (GCP project IDs are globally unique). blcli replaces `prd` in your args with the real ID; you don't edit it by hand.

**Common issues**

| Symptom | Cause and fix |
|---------|---------------|
| Project creation fails with a billing error | Wrong `BillingAccountID`, or the billing account hit its (small) project limit; request an increase in the console |
| `SERVICE_DISABLED` / API not enabled | Newly enabled APIs take a few minutes; wait and apply again |

---

## Stage 2: Environment resources (`terraform/project/`)

**What:** Each environment's network, Kubernetes cluster, domains, and certificates.

Suggested order (also the dependency order):

1. **`main` / `provider` / `variables` / `backend`** — skeleton of every Terraform project
2. **`vpc`** — private network for clusters and databases
3. **`gke`** — Kubernetes cluster. The main pool (1–3 × e2-standard-2, autoscaled) runs the platform components; tainted on-demand and spot pools (e2-standard-4, scale to zero) take apps that add the matching toleration. Spot cuts cost significantly
4. **`ip` / `firewall`** — static ingress IPs and firewall rules
5. **`dns` / `cert`** — DNS records and HTTPS certificates
6. **`artifacts-registry`** — your container images
7. As needed: `iam`, `cdn`, `vpc-peering`, `loki-logs`

Per-component guidance: [terraform/TERRAFORM_PROJECT.md](../terraform/TERRAFORM_PROJECT.md).

**Default components:** `main, backend, config-gcs-tfbackend, provider, variables, vpc, ip, gke, dns, cert, artifacts-registry, outputs` — everything a single environment needs. Add `firewall`, `iam`, `cdn`, `loki-logs` as needed; `vpc-peering` matters only when environments must talk to each other (e.g. a shared corp cluster).

**✅ Checkpoint**

```bash
gcloud container clusters get-credentials prd-cluster --region us-west1 --project <prd project ID>
kubectl get nodes                      # 1 Ready node (e2-standard-2); the two app pools at 0 nodes is expected
gcloud dns managed-zones list --project <prd project ID>     # the public zone's dns_name is your domain
gcloud certificate-manager certificates list --project <prd project ID>   # certificates end up ACTIVE
```

**Common issues**

| Symptom | Cause and fix |
|---------|---------------|
| Certificate stuck in `PROVISIONING` | The domain is not delegated to Cloud DNS yet. Get the NS records with `gcloud dns managed-zones describe <zone> --format='value(nameServers)'` and set them for the domain (or subdomain) at your registrar; the certificate usually turns ACTIVE within tens of minutes |
| Quota errors (`CPUS`, `IN_USE_ADDRESSES`, ...) | New projects have low quotas; request more under IAM & Admin → Quotas |
| `terraform destroy` cannot delete the cluster | `deletionProtection: true` is deliberate; set it to false and apply first if you really want to delete |

---

## Stage 3: Platform components (`kubernetes/`)

**What:** Between "cluster is up" and "app is live" sits a platform layer. `kubernetes/default.yaml` is the default core stack (single `prd` environment); the numeric prefix is the install order:

| Order | Component | What it solves |
|-------|-----------|----------------|
| 0 | `external-secrets-operator` + `external-secrets` | Sync secrets from GCP Secret Manager; no passwords in Git |
| 0 | `sealed-secret` | Encrypt the secrets that must live in Git |
| 2 | `argocd` | GitOps: the cluster matches what's in Git |
| 3–4 | `victoria-metrics-operator` + `victoria-metrics` | Metrics collection, storage (VMSingle) and alerting, all in this cluster |
| 4 | `grafana` | Dashboards (admin password login by default; no Google Workspace needed) |

Optional components (databases, cache, queues, logs, APM, …) are listed in [kubernetes/OPTIONAL_COMPONENTS.md](../kubernetes/OPTIONAL_COMPONENTS.md); add them to `args.yaml` when you need them.

**Small-team tips:**

- **Install from day one:** secret management (external-secrets), ArgoCD, metrics. They get more painful the later you add them.
- **Grafana sign-in:** `auth-mode: password` by default: `kubectl -n grafana port-forward svc/grafana 3000:80`, open http://localhost:3000, and log in as admin with the password from `kubectl -n grafana get secret grafana -o jsonpath='{.data.admin-password}' | base64 -d`. Teams on Google Workspace can switch to `auth-mode: google`.
- **Off by default:** Istio. With one or two services, GKE's built-in Ingress / Gateway is enough. When you need mTLS or canaries, add the `istio` component to `args.yaml` and set `VirtualServiceEnabled: true` on your gitops apps.
- **Metrics storage:** `storage-mode: local` by default keeps metrics in an in-cluster VMSingle. With several environments, switch to `remote` to ship every cluster's metrics to one central cluster (see [examples/multi-env/](../examples/multi-env/)).
- **Databases:** Prefer managed (Cloud SQL) early; enable `cnpg` when you want Postgres in-cluster.

**✅ Checkpoint**

```bash
kubectl get pods -n external-secrets; kubectl get pods -n sealed-secret
kubectl get pods -n argocd; kubectl get pods -n monitoring-vm; kubectl get pods -n grafana
                                       # all Running / Completed
kubectl get clustersecretstore gcp-secret-store         # READY True: the cluster can read Secret Manager
kubectl -n monitoring-vm get vmsingle,vmagent,vmalert   # all operational
kubectl -n grafana port-forward svc/grafana 3000:80     # open http://localhost:3000, log in as admin
kubectl -n argocd port-forward svc/argocd-server 8080:443   # open https://localhost:8080, log in with GitHub
```

**Common issues**

| Symptom | Cause and fix |
|---------|---------------|
| `gcp-secret-store` not Ready | Workload Identity mismatch: the component's `ClusterName` must equal the GKE cluster name in Terraform (both `prd-cluster` by default); also check that stage 2 created `sa-sm-accessor` |
| ExternalSecret shows `SecretSyncedError` | The secret does not exist in Secret Manager yet (e.g. `slack-webhook-url-infra-alert`); create it and wait for the next sync |
| Pods stuck in `Pending` | Not enough node capacity; `kubectl describe pod` shows why. The main pool scales to 3 nodes; beyond that raise `machineType` |
| ArgoCD install script exits, or nobody can log in afterwards | See the stage 0 table: GitHub App ID / Installation ID, Dex Client ID and org |

---

## Stage 4: Applications (`gitops/`)

**What:** Describe your apps as Deployment / StatefulSet + Service + ConfigMap, and generate ArgoCD Applications that ArgoCD syncs to the cluster.

`gitops/default.yaml` ships a `hello-world` example. Replace it with your own app: name, image, ports, health checks.

```bash
blcli apply gitops -d ./workspace/output/gitops --args args.yaml
```

**Why:** Every release becomes a Git commit; rollback is `git revert`. Who changed what, and when, is always on record.

**✅ Checkpoint**

```bash
kubectl -n argocd get applications     # hello-world is Synced + Healthy
kubectl -n app get pods                # the app's pods are Running
```

**Common issues**

| Symptom | Cause and fix |
|---------|---------------|
| Application shows `repository not found` / `ComparisonError` | `SourceRepoURL` is still the sample `example-org/gitops`; point it at your gitops repo and make sure the GitHub App is installed on it |
| Sync fails with `no matches for kind "VirtualService"` | The app sets `VirtualServiceEnabled: true` but the cluster has no Istio; remove it or install the `istio` component first |
| Sync rejected for a repo or namespace | ArgoCD's `apps` project only allows the configured gitops repos and the app namespace; add yours with the argocd parameters `AppProjectSourceRepos` / `AppProjectNamespaces` |

---

## Stage 5: Generate, push, deploy

```bash
# 1. Render everything from args.yaml
blcli init -r github.com/ggsrc/bl-template -a args.yaml --output ./workspace/output

# 2. Push the generated terraform / kubernetes / gitops repos to GitHub
blcli apply init-repos -o <your-github-org> -d ./workspace/output

# 3. Deploy layer by layer (preview with --dry-run first)
blcli apply terraform  -d ./workspace/output/terraform --dry-run
blcli apply terraform  -d ./workspace/output/terraform
blcli apply kubernetes -d ./workspace/output/kubernetes -r github.com/ggsrc/bl-template
blcli apply gitops     -d ./workspace/output/gitops --args args.yaml
# or all at once: blcli apply all -d ./workspace/output --args args.yaml

# 4. Check status
blcli status --args args.yaml
```

If something goes wrong, `blcli rollback` reverts (preview first, e.g. `blcli rollback terraform --args args.yaml --dry-run`).

---

## Once you understand it: make it yours

This repo is meant to be a **forkable reference implementation**. With the four layers in mind you can:

- Add resource templates under `terraform/project/` and register them in `terraform/config.yaml`
- Add components under `kubernetes/components/` and register them (with dependencies) in `kubernetes/config.yaml`
- Edit the `args.yaml` files so parameter descriptions match how your team works

No changes to blcli itself are needed.

---

## FAQ

**I'm a solo developer — is this too heavy?**
The default is already one environment with the core components; trim further per the small-team tips above. For the lightest possible setup, start with [bl-template-personal](https://github.com/ggsrc/bl-template-personal) and move to this template as your team grows — both speak the same blcli protocol.

**Can I use it without a GCP Organization?**
Yes. Set `OrganizationID` to `"0"` and use a Billing Account only.

**What does it cost?**
Mostly GKE nodes and load balancers. Idle, the default runs a single e2-standard-2 node, with both app pools scaled to zero; put stateless apps on the spot pool for the lowest cost. Check current GCP pricing for numbers.
