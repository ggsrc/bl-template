# Multi-environment example (stg / prd / corp)

The template's `default.yaml` files start you on **one environment** (`prd`). These files are the
layout a growing team usually ends up with, kept here as a reference:

| Environment | Role |
|-------------|------|
| `prd` | Production cluster and workloads |
| `stg` | Staging / pre-release |
| `corp` | Shared internal services: Grafana, central VictoriaMetrics, Artifact Registry, CDN, GitOps service account |

What changes compared with the single-environment default:

- **Terraform** (`terraform.default.yaml`): three GCP projects, VPC peering between `corp` and each
  environment, the Artifact Registry and shared IAM in `corp`.
- **Kubernetes** (`kubernetes.default.yaml`): Istio in every cluster; `victoria-metrics-operator` uses
  `storage-mode: remote`, so `prd` and `stg` only scrape and ship metrics to the central cluster in
  `corp`, where Grafana runs. The central VictoriaMetrics cluster itself is not part of these files.
- **GitOps** (`gitops.default.yaml`): apps deployed to both `stg` and `prd`.

## How to use it

`blcli init-args` always reads the template's own `default.yaml`. To start from this layout, generate
your `args.yaml` as usual, then copy the `terraform`, `kubernetes` and `gitops` sections you need from
these files into it, and run `blcli check args` before `blcli init`.

CI renders this layout on every pull request (`scripts/test-defaults.py`) and checks that it still installs Istio, ships metrics to `corp` and keeps Google sign-in.
