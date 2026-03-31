# Terraform Project Configuration Guide

Chinese version: [TERRAFORM_PROJECT_zh.md](./TERRAFORM_PROJECT_zh.md)

## Required Components and When `main` Is Needed

- No component is marked as strictly required in `config.yaml`; each project's `components` list in `default.yaml` determines what is included.
- `main` provides core `locals` (`project_id`, `region`, `project_name`, `domain`, `vpc_name`). Any project using `vpc` or `cert` should include `main`, because cert templates use `local.project_id`, and `main` defines `vpc_name = google_compute_network.main.name` for cross-resource references.
- `provider` and `variables` are typically required for any project that runs Terraform (that is, any component producing `.tf` files), because they define variables and provider setup (`project_id`, `region`, `zone`, etc.).

## Recommended Components by Project Type

| Project | Purpose | Recommended components |
|------|------|----------|
| **prd** | Production environment, Kubernetes + workloads | main, config-gcs-tfbackend, provider, variables, vpc, ip, firewall, gke, dns, cert, outputs (optional: iam) |
| **stg** | Staging / pre-production | main, config-gcs-tfbackend, provider, variables, vpc, gke, dns, cert (optional: ip, firewall, outputs) |
| **corp** | Shared infrastructure (grafana, bytebase, Artifact Registry, CDN, GitOps SA) | main, config-gcs-tfbackend, provider, variables, vpc, gke, dns, cert, loki-logs, artifacts-registry, cdn, iam |

## Backend

- **Full backend block**: If a project directory should use GCS backend directly, include the `backend` component. It renders `backend.tf` with a full `terraform { backend "gcs" { ... } }` block, so `terraform init` and `terraform apply` can run directly.
- **backend-config fragment**: The `config-gcs-tfbackend` component only generates `bucket` and `prefix` lines, intended for `terraform init -backend-config=config.gcs.tfbackend`. In this mode, you still need to provide a complete backend declaration separately (for example via a dedicated `backend.tf` or CLI options). If you want each project directory to be self-contained, use `backend`.

## Multi-subnet (`subnetworks`) Naming Convention

- When using the `vpc` component with a `subnetworks` array, each subnet `name` must be a valid Terraform/HCL resource identifier.
- Prefer lowercase letters, digits, and underscores only (for example `us_west1`). Avoid hyphens; if hyphens are used, sanitize names before using them as Terraform resource names (for example replace `-` with `_`) to avoid parsing errors.

## OrganizationID and `org_id`

- `OrganizationID` (`terraform.global.OrganizationID` in args): when set to `"0"` or `0`, init templates do not render any `org_id`-related content.
- Effect: `variable "gcp_common"` has no `org_id` field/default, and resources such as `google_project` omit `org_id` lines. This is suitable for environments without an Organization and with Billing Account only.
- Parameter defaults: `OrganizationID` is optional and defaults to `"0"` in both `terraform/args.yaml` and `terraform/init/args.yaml`.

## Avoid Duplicate Outputs and Locals

- **Gateway IP and related outputs**: output only through the `ip` component via `output_addresses`; the `outputs` component no longer includes `gateway_ips` to avoid duplication with `ip.tf`.
- **`vpc_name`**: define only in `main.tf` via `locals { vpc_name = google_compute_network.main.name }`; `vpc.tf` should not define duplicate locals and should use parameter `vpc_name` directly.
