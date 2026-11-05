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

## DNSSEC for Public Zones

- The `dns` component turns DNSSEC on (`dnssec_config { state = "on" }`) for every zone with `visibility: public` that has no `dnssec_config`. Private zones get none. To opt out, set `dnssec_config.state: "off"` on the zone.
- Cloud DNS signs the zone right away, but resolvers only validate the signatures once a DS record for the zone exists in the parent zone. Until then the zone resolves as before, without DNSSEC protection.
- Publish the DS record after `terraform apply`:
  1. Find the key-signing key: `gcloud dns dns-keys list --zone=ZONE_NAME --project=PROJECT_ID` (type `keySigning`).
  2. Print its DS record: `gcloud dns dns-keys describe KEY_ID --zone=ZONE_NAME --project=PROJECT_ID --format='value(ds_record())'`.
  3. Add that DS record where the zone is delegated: at the domain registrar for a registered domain (for example `example.com.`), or as a `DS` record set in the parent zone for a delegated subdomain (for example `prd.example.com.` inside `example.com.`).
- To turn DNSSEC off later, first remove the DS record from the registrar or parent zone and wait until its TTL has expired, then set the state to `off`. Turning it off while the DS record is still published makes validating resolvers fail for the whole zone.

## TLS Policy for the CDN HTTPS Proxy

- The `cdn` component attaches an SSL policy to each HTTPS proxy: profile `MODERN`, minimum TLS 1.2. Without a policy Google Cloud load balancers accept TLS 1.0 (`COMPATIBLE` profile).
- `MODERN` keeps the ECDHE cipher suites used by current browsers and TLS 1.2 clients. Set `ssl_policy_profile: RESTRICTED` to also drop the CBC suites, or `ssl_min_tls_version: TLS_1_3` (requires `RESTRICTED`) if every client supports TLS 1.3.
