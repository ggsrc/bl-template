<div align="center">

# bl-template

**一份配置，走完云平台全链路。**

*One config. Full cloud platform lifecycle.*

面向 [blcli](https://github.com/ggsrc/blcli) 的企业级平台模板 — **当前以 GCP 为首个完整实现**，一份自描述仓库覆盖 Terraform、Kubernetes 与 ArgoCD GitOps。

[![GitHub stars](https://img.shields.io/github/stars/ggsrc/bl-template?style=flat-square)](https://github.com/ggsrc/bl-template/stargazers)
[![GitHub forks](https://img.shields.io/github/forks/ggsrc/bl-template?style=flat-square)](https://github.com/ggsrc/bl-template/network/members)
[![blcli](https://img.shields.io/badge/powered%20by-blcli-blue?style=flat-square)](https://github.com/ggsrc/blcli)
[![个人版模板](https://img.shields.io/badge/个人版-bl--template--personal-green?style=flat-square)](https://github.com/ggsrc/bl-template-personal)

[快速开始](#blcli-用法说明) · [英文文档](README.md) · [ARGS_DESIGN](ARGS_DESIGN.md)

</div>

<!-- ADOPTION:START -->
**采用情况（2026-07-13）：** 1 GitHub Stars · 0 Forks · 配合 [blcli](https://github.com/ggsrc/blcli) 使用
<!-- ADOPTION:END -->

---

## bl-template 是什么？

[blcli](https://github.com/ggsrc/blcli) 的**企业版**官方模板仓。在 GCP Organization 下生成多项目、多环境基础设施：Terraform 管云资源，Kubernetes 管平台组件，GitOps 管 ArgoCD 应用。结构由 `config.yaml`、`args.yaml` 与 Go 模板定义。

```
bl-template  +  args.yaml  +  blcli  →  corp / stg / prd  →  用 blcli apply 部署
```

可 fork 本仓定制模块与组件，无需修改 blcli 本身。

---

## 适合谁？

| 用户 | 何时选用 bl-template |
|------|----------------------|
| 平台 / SRE 团队 | 多项目 GCP（如 corp、stg、prd）、生产级 ArgoCD GitOps |
| 已标准化 blcli 的团队 | 需要可 fork 的参考实现 |
| 个人开发者 | 请用 [bl-template-personal](https://github.com/ggsrc/bl-template-personal) |

---

## 为什么选这个模板？

- **自描述** — `config.yaml` 声明组件与依赖；`args.yaml` 描述参数，供 `init-args` / `explain` 使用。
- **全栈** — Terraform（init / projects / modules）+ Kubernetes（核心栈 + 可选组件）+ GitOps（应用模板与 ArgoCD Application）。
- **约定优于配置** — 从 `path` 发现 args、config 里声明依赖顺序、`default.yaml` 提供默认值。
- **为 blcli 设计** — 适配 `init-args → init → apply → status → rollback`，不是纯 Terraform 蓝图。

| 没有 bl-template | 有 bl-template |
|---|---|
| 手工拼 CFT 模块 + K8s 清单 + ArgoCD | 一个可 fork 仓库 + 一份 args |
| 参数无文档 | `args.yaml` + [ARGS_DESIGN.md](./ARGS_DESIGN.md) |
| 安装顺序靠经验 | `config.yaml` 的 `dependencies`，由 blcli 执行 |

---

## 和常见方案怎么比？

| 方案 | 范围 | bl-template |
|------|------|-------------|
| [CFT](https://github.com/GoogleCloudPlatform/cloud-foundation-toolkit) / [Fabric FAST](https://github.com/GoogleCloudPlatform/cloud-foundation-fabric) | 企业 GCP Landing Zone（Terraform） | 增加与 blcli 集成的 K8s + GitOps 模板 |
| [Kubestack catalog](https://github.com/kbst/catalog) | Terraform 中的 Kustomize 服务 | 外部模板仓 + args 协议；默认面向 GCP |
| 自建模块拼装 | 完全自控 | 约定、文档与 blcli 集成开箱即用 |

---

## 谁在用？

欢迎补充早期案例。若你在生产或实验中 fork/使用本模板，请 [提 PR 编辑 README.md](https://github.com/ggsrc/bl-template/edit/main/README.md)（logo 可选）；列表会自动同步到本页。

<!-- ADOPTERS:START -->
<!-- Example:
- [Your Org](https://example.com) — GCP platform on blcli + bl-template
-->
<!-- ADOPTERS:END -->

---

# bl-template（技术文档）

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
├── kubernetes/         # Kubernetes 配置
│   ├── config.yaml     # 已注册的全部组件（核心 + 可选）
│   ├── default.yaml    # init-args 默认启用的核心栈
│   ├── OPTIONAL_COMPONENTS.md  # 可选组件说明
│   └── components/     # 组件模板（Helm / Kustomize）
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

定义 Kubernetes 平台全部组件。**核心栈**由 `default.yaml` 提供（多环境 prd/stg/corp）。**可选组件**仅在 `config.yaml` 注册，默认不写入 args — 详见 [kubernetes/OPTIONAL_COMPONENTS.md](kubernetes/OPTIONAL_COMPONENTS.md)。

**核心（default.yaml 典型）：** external-secrets-operator、external-secrets、sealed-secret、istio、argocd、victoria-metrics-operator、victoria-metrics、grafana（corp）

**可选（在 args.yaml 中 opt-in）：** cnpg、redis、paradedb、kafka、juicefs、loki、otel-collector、uptrace、n9e、bytebase；bl-template 另含 web-ide、navigation。均使用官方上游镜像。

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

**v1.5 增强：**

```bash
# 交互式向导
blcli init-args -r ./bl-template --wizard -o workspace/config/args.yaml

# 仅预览，不写文件
blcli init-args -r ./bl-template --preview -o workspace/config/args.yaml

# 校验 args（init 前）
blcli check args --args workspace/config/args.yaml -r ./bl-template
```

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

### 5. CI 校验（GitHub Actions）

本仓库提供 `.github/workflows/blcli-validate.yml` 样板：在 PR 中预览 args 并运行 `blcli check args`。详见 [blcli CI 文档](https://github.com/ggsrc/blcli/blob/main/docs/zh/CI.md)。

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
