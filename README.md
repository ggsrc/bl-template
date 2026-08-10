<div align="center">

# bl-template

**One config. Full cloud platform lifecycle.**

*一份配置，走完云平台全链路。*

Enterprise **GCP-first** platform template for [blcli](https://github.com/ggsrc/blcli) — Terraform, Kubernetes, and ArgoCD GitOps from one self-describing repository.

[![GitHub stars](https://img.shields.io/github/stars/ggsrc/bl-template?style=flat-square)](https://github.com/ggsrc/bl-template/stargazers)
[![GitHub forks](https://img.shields.io/github/forks/ggsrc/bl-template?style=flat-square)](https://github.com/ggsrc/bl-template/network/members)
[![blcli](https://img.shields.io/badge/powered%20by-blcli-blue?style=flat-square)](https://github.com/ggsrc/blcli)
[![Personal template](https://img.shields.io/badge/personal-bl--template--personal-green?style=flat-square)](https://github.com/ggsrc/bl-template-personal)

[Quick Start](#blcli-usage) · [中文说明](README_zh.md) · [ARGS_DESIGN](ARGS_DESIGN.md)

</div>

<!-- ADOPTION:START -->
**Adoption snapshot (2026-08-10):** 1 GitHub stars · 0 forks · powered by [blcli](https://github.com/ggsrc/blcli)
<!-- ADOPTION:END -->

For Chinese documentation, see [README_zh.md](./README_zh.md).

---

## What is bl-template?

Official **enterprise** template repository for [blcli](https://github.com/ggsrc/blcli). Use it under a GCP Organization to generate multi-project, multi-environment infrastructure — Terraform for GCP resources, Kubernetes platform components, and ArgoCD GitOps applications — from `config.yaml`, `args.yaml`, and Go templates.

```
bl-template  +  args.yaml  +  blcli  →  corp / stg / prd  →  apply with blcli
```

Fork this repo to customize modules and components while keeping the same blcli protocol.

---

## Who is it for?

| Audience | When to use bl-template |
|----------|-------------------------|
| Platform / SRE teams | Multi-project GCP org (e.g. corp, stg, prd), production GitOps with ArgoCD |
| Teams standardizing on blcli | Want a batteries-included reference implementation to fork |
| Not you? | Solo developers → use [bl-template-personal](https://github.com/ggsrc/bl-template-personal) instead |

---

## Why this template?

- **Self-describing** — `config.yaml` declares components and dependencies; `args.yaml` documents every parameter for `blcli init-args` and `explain`.
- **Full stack** — Terraform init + projects + modules, Kubernetes base/optional components, GitOps app templates and ArgoCD Applications.
- **Convention over configuration** — args discovery from `path`, dependency ordering in config, `default.yaml` for sensible defaults.
- **blcli-native** — Designed for `init-args` → `init` → `apply` → `status` → `rollback`; not a standalone Terraform-only blueprint.

| Without bl-template | With bl-template |
|---|---|
| Assemble CFT modules + K8s manifests + ArgoCD by hand | One forkable repo, one args file |
| Undocumented parameters | `args.yaml` + [ARGS_DESIGN.md](./ARGS_DESIGN.md) |
| Unknown install order | `dependencies` in `config.yaml`, enforced by blcli |

---

## How it compares

| Approach | Scope | bl-template |
|----------|-------|-------------|
| [CFT](https://github.com/GoogleCloudPlatform/cloud-foundation-toolkit) / [Fabric FAST](https://github.com/GoogleCloudPlatform/cloud-foundation-fabric) | Enterprise GCP landing zone (Terraform) | Adds Kubernetes + GitOps templates wired for blcli |
| [Kubestack catalog](https://github.com/kbst/catalog) | Kustomize services in Terraform | External template repo + args protocol; GCP-focused defaults |
| DIY fork of public modules | Full control | Opinionated layout, docs, and blcli integration out of the box |

---

## Who uses bl-template?

We are collecting adopters. If you fork or run this template in production, [open a PR](https://github.com/ggsrc/bl-template/edit/main/README.md) to add your org below (logo optional). The list is mirrored to [README_zh.md](README_zh.md) automatically.

<!-- ADOPTERS:START -->
<!-- Example:
- [Your Org](https://example.com) — GCP platform on blcli + bl-template
-->
<!-- ADOPTERS:END -->

---

## Repository Purpose

This is a template repository for the `blcli` tool, used to quickly generate brand new infrastructure configurations under a GCP Organization. Through templating, it can quickly create:

- **Terraform Configurations**: Infrastructure as code configurations for GCP resources
- **Kubernetes Configurations**: Initialization components and optional components for Kubernetes clusters
- **GitOps Configurations**: Basic templates for GitOps workflows

## Design Architecture

### Core Design Principles

1. **Templating**: All configuration files use Go Template syntax with parameterization support
2. **Self-describing**: Parameter self-description through `config.yaml` and `args.yaml`
3. **Modular**: Components are categorized by function, supporting dependency management and independent deployment
4. **Convention over Configuration**: Follow the principle of convention over configuration to reduce explicit configuration

### Directory Structure

```
bl-template/
├── terraform/          # Terraform infrastructure configurations
│   ├── config.yaml     # Terraform component configuration definitions
│   ├── init/           # GCP Organization level initialization
│   ├── modules/         # Reusable Terraform modules
│   ├── project/        # Project-level Terraform configurations
│   └── projects/       # Project deployment configurations
├── kubernetes/         # Kubernetes configurations
│   ├── config.yaml     # All registered components (core + optional)
│   ├── default.yaml    # Default components for init-args (core stack only)
│   ├── OPTIONAL_COMPONENTS.md  # Opt-in components reference
│   └── components/     # Component templates (Helm / Kustomize)
├── gitops/             # GitOps configurations
│   ├── config.yaml     # app-templates (deployment/statefulset) and argocd definitions
│   ├── args.yaml       # parameter definitions (including ArgoCD Application fields)
│   ├── default.yaml    # defaults: argocd.project and apps[] (name, kind, image, repo, project...)
│   ├── app.yaml.tmpl   # ArgoCD Application template
│   └── base-*.tmpl     # base templates for deployment/statefulset/service/configmap
└── README.md           # this file
```

## Core Components

### 1. config.yaml

The `config.yaml` in each directory describes the template components provided by that directory and their purposes.

#### terraform/config.yaml

Defines three main sections:

- **init**: GCP Organization level initialization
  - `projects`: Create GCP projects and enable services
  - Set `OrganizationID` to `"0"` in args to omit `org_id` in generated variables and resources (see [terraform/TERRAFORM_PROJECT.md](terraform/TERRAFORM_PROJECT.md)).
  
- **modules**: Reusable Terraform modules (only for template generation)
  - `gke`: GKE cluster module
  - `gke-node-pool`: GKE node pool module
  - `vm-server`: VM server module
  - `ssl-cert`: SSL certificate module
  - `tailscale-node`: Tailscale node module
  - `tailscale-exit-node`: Tailscale exit node module
  - `tailscale-subnet-router`: Tailscale subnet router module
  - `gke-sm-accessor-sa`: GKE Secret Manager accessor service account module
  - `security-policy-corp-ip-whitelist`: Security policy corporate IP whitelist module

- **projects**: Project-level deployment configurations (includes actual deployment dependency order)
  - `main`: Main configuration file
  - `modules`: Module usage examples
  - `outputs`: Output definitions
  - `gke`: GKE deployment configuration
  - `backend`: Terraform backend configuration
  - `variables`: Variable definitions
  - `provider`: Provider configuration

#### kubernetes/config.yaml

Defines all Kubernetes platform components. **Core stack** entries come from `default.yaml` (multi-env prd/stg/corp). **Optional** components are registered here but not enabled by default — see [kubernetes/OPTIONAL_COMPONENTS.md](kubernetes/OPTIONAL_COMPONENTS.md).

**Core (typical default.yaml):** external-secrets-operator, external-secrets, sealed-secret, istio, argocd, victoria-metrics-operator, victoria-metrics, grafana (corp)

**Optional (opt-in via args.yaml):**

| Component | Official image / chart | Notes |
|-----------|------------------------|--------|
| cnpg | CloudNativePG Operator | PostgreSQL operator |
| redis | Bitnami Redis | Shared cache |
| paradedb | ParadeDB | Requires cnpg |
| kafka | Bitnami Kafka | Message queue |
| juicefs | juicedata/mount | S3 gateway (Kustomize) |
| loki | Grafana Loki chart | Log aggregation |
| otel-collector | OpenTelemetry Collector | Observability pipeline |
| uptrace | uptrace/uptrace | APM |
| n9e | flashcatcloud/nightingale | Monitoring / alerting |
| bytebase | bytebase/bytebase | DB schema management |
| web-ide | codercom/code-server | Browser IDE (bl-template only) |
| navigation | b4bz/homer | Internal links dashboard (bl-template only) |

#### gitops/config.yaml

Defines GitOps templates and ArgoCD configuration:

- **app-templates**: Base application templates
  - `deployment`: Deployment-style applications (path/args point to template and parameters)
  - `statefulset`: StatefulSet-style applications
- **argocd**: ArgoCD-related templates (for example `app.yaml.tmpl` to generate ArgoCD Application resources)

Used together with `gitops/args.yaml` and `gitops/default.yaml`. `default.yaml` provides defaults and includes `argocd.project` and `apps[]` (each app contains fields such as name, kind, image, repo, and project).

### 2. args.yaml

`args.yaml` is used to describe template parameters, implementing parameter self-description functionality.

#### Discovery Mechanism

1. **Convention First**: CLI automatically infers based on `path` in `config.yaml`
   - If `path` is a directory → look for `{path}/args.yaml`
   - If `path` is a file → look for `{dirname(path)}/args.yaml`

2. **Explicit Specification**: Optional `args` field in `config.yaml` to explicitly specify the path

3. **Hierarchical Lookup**: Supports upward lookup of parent directory's `args.yaml` for parameter inheritance

#### Structure Example

```yaml
version: 1.0.0

parameters:
  # Global parameters
  global:
    OrganizationID:
      type: string
      description: "GCP Organization ID"
      required: true
      example: "123456789012"
  
  # Component-level parameters
  components:
    gke:
      project_id:
        type: string
        description: "GCP Project ID"
        required: true
      cluster_name:
        type: string
        description: "Name of the GKE cluster"
        required: true
        pattern: "^[a-z0-9-]+$"
```

#### Parameter Validation

Parameters support **validation rules** that blcli enforces during `blcli init` (before writing any files):

- **validation** (list): Each rule is a map with `kind` and kind-specific params. Supported kinds: `required`, `stringLength`, `pattern`, `format`, `enum`, `numberRange`.
- **validation.unique** (top-level): Ensures uniqueness at a path (e.g. `terraform.projects[].name`).

Example:

```yaml
parameters:
  global:
    ProjectName:
      type: string
      required: true
      validation:
        - kind: required
        - kind: stringLength
          min: 6
          max: 30
          message: "GCP project ID: 6-30 characters"
        - kind: pattern
          value: "^[a-z][a-z0-9-]{4,28}[a-z0-9]$"

# Top-level: ensure project names are unique
validation:
  unique:
    - path: "terraform.projects[].name"
      message: "Project names must be unique"
```

See [ARGS_DESIGN.md](./ARGS_DESIGN.md) for full parameter and validation documentation.

For detailed design, please refer to [ARGS_DESIGN.md](./ARGS_DESIGN.md)

## blcli Usage

This repository is used as a `blcli` template repository through `-r`, either with a local path or a GitHub URL.

### 1. Generate parameter file (`init-args`)

Collect parameter definitions from multiple `args.yaml` levels in the template repository, and generate an editable `args.yaml`:

```bash
blcli init-args -r github.com/ggsrc/bl-template -o args.yaml
# Or use a local path
blcli init-args -r /path/to/bl-template -o args.yaml
```

The generated `args.yaml` includes sections such as `global`, `terraform`, `kubernetes`, and `gitops` (depending on template `config/args` definitions).

### 2. Generate infrastructure configuration (`init`)

Generate Terraform, Kubernetes, and GitOps configuration from `args.yaml` and templates:

```bash
# Generate all modules (terraform + kubernetes + gitops, if present in args)
blcli init -r github.com/ggsrc/bl-template -a args.yaml

# Generate terraform only
blcli init terraform -r github.com/ggsrc/bl-template -a args.yaml

# Generate kubernetes only
blcli init kubernetes -r github.com/ggsrc/bl-template -a args.yaml

# Generate with custom output and overwrite
blcli init -r /path/to/bl-template -a args.yaml --output ./workspace/output -w
```

- **Terraform**: Output to `{workspace}/terraform/` (init, gcp projects, modules, etc.).
- **Kubernetes**: Output to `{workspace}/kubernetes/{project}/{component}/` based on `kubernetes.projects[]` and `components`.
- **GitOps**: When `args.yaml` includes `gitops.argocd` and `gitops.apps`, output by project × app into `{workspace}/gitops/{project}/{app_name}/`, including deployment/statefulset, service, configmap, and `app.yaml` (ArgoCD Application).

### 3. Apply GitOps (`apply gitops`)

Run `kubectl apply` on ArgoCD Applications in the generated GitOps directory. Actual app deployment is synced by ArgoCD:

```bash
blcli apply gitops -d ./workspace/output/gitops --args args.yaml
```

### 4. Initialize and push repositories to GitHub (`apply init-repos`)

For `terraform`, `kubernetes`, and `gitops` directories generated by `blcli init`, run `git init`, create GitHub repositories, commit, and push (interactive `Y` confirmations required):

```bash
blcli apply init-repos -o myorg -d ./workspace/output
```

Requires [gh](https://cli.github.com/) installed and authenticated (`gh auth login`).

## Template Syntax

All template files use Go Template syntax, supporting:

- Variable substitution: `{{ .ProjectName }}`
- Conditional statements: `{{ if .Condition }}...{{ end }}`
- Loops: `{{ range .Items }}...{{ end }}`
- Function calls: `{{ .Function | format }}`

Example:

```hcl
# terraform/project/main.tf.tmpl
resource "google_compute_instance" "example" {
  name         = "{{ .ProjectName }}-instance"
  machine_type = "e2-medium"
  zone         = var.zone
}
```

## Dependency Management

The `dependencies` field in `config.yaml` defines dependency relationships between components:

```yaml
projects:
  - name: gke
    dependencies:
      - vpc  # gke depends on vpc
```

The CLI will automatically sort based on dependency relationships, ensuring dependent components are deployed before components that depend on them.

## Extension Guide

### Adding New Modules

1. Create module directory under `terraform/modules/`
2. Add module definition in the `modules` section of `terraform/config.yaml`
3. Create `args.yaml` to describe module parameters (optional)

### Adding New Components

1. Create component template file (`.tmpl`)
2. Add component definition in the corresponding `config.yaml`
3. Add parameter definitions in `args.yaml` (if needed)

### Modifying Parameter Definitions

Edit the `args.yaml` file in the corresponding directory to add or modify parameter definitions.

## Version Management

- Both `config.yaml` and `args.yaml` contain `version` fields for version control
- Template files use semantic versioning

## Contributing Guide

1. Follow existing directory structure and naming conventions
2. Add complete `args.yaml` definitions for new components
3. Update component list in `config.yaml`
4. Add necessary dependency relationships
5. Provide clear parameter descriptions and examples

## Related Documentation

- [args.yaml Design Document](./ARGS_DESIGN.md): Detailed parameter self-description design document
