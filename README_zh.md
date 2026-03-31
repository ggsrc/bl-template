# bl-template

blcli template repository for one-click generation of GCP environment infrastructure configurations.

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
│   ├── config.yaml     # Kubernetes component configuration definitions
│   ├── base/           # Base components (required)
│   └── optional/        # Optional components
├── gitops/             # GitOps configurations
│   ├── config.yaml     # app-templates（deployment/statefulset）、argocd 组件定义
│   ├── args.yaml       # 参数定义（含 ArgoCD Application 相关）
│   ├── default.yaml    # 默认值：argocd.project、apps[]（name、kind、image、repo、project 等）
│   ├── app.yaml.tmpl   # ArgoCD Application 模板
│   └── base-*.tmpl     # deployment/statefulset/service/configmap 等基础模板
└── README.md           # 本文件
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

Defines Kubernetes cluster initialization components:

- **init**: Initialization components (required)
  - `namespace`: Namespace
  - `istio`: Service mesh
  - `victoria-metrics`: Monitoring system

- **optional**: Optional components
  - `cnpg`: CloudNativePG database operator
  - `web-ide`: Web IDE
  - `redis`: Redis
  - `kiali`: Service mesh visualization

#### gitops/config.yaml

定义 GitOps 模板与 ArgoCD 配置：

- **app-templates**：应用基础模板
  - `deployment`：Deployment 类应用（path、args 指向模板与参数）
  - `statefulset`：StatefulSet 类应用
- **argocd**：ArgoCD 相关模板（如 app.yaml.tmpl，用于生成 ArgoCD Application）

配合 `gitops/args.yaml` 与 `gitops/default.yaml` 使用。`default.yaml` 提供默认值，结构包含 `argocd.project` 与 `apps[]`（每个 app 含 name、kind、image、repo、project 等）。

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

## blcli 用法说明

本仓库作为 blcli 的模板仓库，通过 `-r` 指定本地路径或 GitHub 地址使用。

### 1. 生成参数文件（init-args）

从模板仓库收集各层 `args.yaml` 定义，生成一份可编辑的 `args.yaml`：

```bash
blcli init-args -r github.com/ggsrc/bl-template -o args.yaml
# 或使用本地路径
blcli init-args -r /path/to/bl-template -o args.yaml
```

生成的 `args.yaml` 包含 `global`、`terraform`、`kubernetes`、`gitops` 等段（取决于模板中的 config/args 定义）。

### 2. 生成基础设施配置（init）

根据 `args.yaml` 和模板生成 Terraform、Kubernetes、GitOps 配置：

```bash
# 生成全部（terraform + kubernetes + gitops，若 args 中有对应段）
blcli init -r github.com/ggsrc/bl-template -a args.yaml

# 只生成 terraform
blcli init terraform -r github.com/ggsrc/bl-template -a args.yaml

# 只生成 kubernetes
blcli init kubernetes -r github.com/ggsrc/bl-template -a args.yaml

# 生成时指定输出目录与覆盖
blcli init -r /path/to/bl-template -a args.yaml --output ./workspace/output -w
```

- **Terraform**：输出到 `{workspace}/terraform/`（init、gcp 项目、modules 等）。
- **Kubernetes**：按 `kubernetes.projects[]` 与 `components` 输出到 `{workspace}/kubernetes/{project}/{component}/`。
- **GitOps**：当 `args.yaml` 含 `gitops.argocd` 与 `gitops.apps` 时，按 project × app 输出到 `{workspace}/gitops/{project}/{app_name}/`，包含 deployment/statefulset、service、configmap、`app.yaml`（ArgoCD Application）等。

### 3. 应用 GitOps（apply gitops）

对生成的 GitOps 目录中的 ArgoCD Application 执行 `kubectl apply`，实际应用由 ArgoCD 同步部署：

```bash
blcli apply gitops -d ./workspace/output/gitops --args args.yaml
```

### 4. 初始化仓库并推送到 GitHub（apply init-repos）

对 `blcli init` 生成的 terraform、kubernetes、gitops 三个目录分别执行 git init、创建 GitHub 仓库、提交并推送（需在提示时输入 Y 确认）：

```bash
blcli apply init-repos -o myorg -d ./workspace/output
```

需要已安装并登录 [gh](https://cli.github.com/)（`gh auth login`）。

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
