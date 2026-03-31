# Terraform 项目级配置说明

## 组件是否必须、何时需要 main

- **config.yaml 中未标记任何组件为“必须”**，是否包含某组件由各项目在 default.yaml 的 `components` 列表中决定。
- **main**：提供 `locals`（project_id、region、project_name、domain、vpc_name）。凡使用 **vpc** 或 **cert** 的项目都应包含 **main**，因为 cert 模板会使用 `local.project_id`，且 main 中 `vpc_name = google_compute_network.main.name` 供其他资源引用。
- **provider、variables**：只要项目会执行 Terraform（任一组件产出 .tf），通常都需要，用于 project_id、region、zone 等变量与 provider 配置。

## 各项目类型建议组件

| 项目 | 用途 | 建议组件 |
|------|------|----------|
| **prd** | 生产环境，K8s + 业务 | main, config-gcs-tfbackend, provider, variables, vpc, ip, firewall, gke, dns, cert, outputs（可选 iam） |
| **stg** | 测试/预发环境 | main, config-gcs-tfbackend, provider, variables, vpc, gke, dns, cert（可选 ip, firewall, outputs） |
| **corp** | 公用组件（grafana、bytebase、Artifact Registry、CDN、GitOps SA） | main, config-gcs-tfbackend, provider, variables, vpc, gke, dns, cert, loki-logs, artifacts-registry, cdn, iam |

## Backend

- **完整 backend 块**：项目目录下如需使用 GCS 后端，应在组件列表中包含 **backend** 组件。该组件会渲染 `backend.tf`，产出完整的 `terraform { backend "gcs" { ... } }` 块，可直接执行 `terraform init` 与 `terraform apply`。
- **backend-config 片段**：**config-gcs-tfbackend** 组件仅生成 `bucket` 与 `prefix` 两行，适用于 `terraform init -backend-config=config.gcs.tfbackend` 的用法；此时项目目录内仍需通过其他方式（例如单独维护的 `backend.tf` 或 CLI 参数）提供完整 backend 配置。若希望项目目录自包含、可直接 `terraform init`，请使用 **backend** 组件。

## 多子网（subnetworks）命名约定

- 使用 **vpc** 组件的 `subnetworks` 数组配置多子网时，每个子网的 `name` 必须是合法的 Terraform/HCL 资源标识符。
- 建议仅使用小写字母、数字和下划线（如 `us_west1`），避免使用连字符；若使用连字符，需在模板或调用侧对 `name` 做 sanitize（例如替换为下划线）后再作为 Terraform 资源名使用，否则可能引发解析错误。

## OrganizationID 与 org_id

- **OrganizationID**（`terraform.global.OrganizationID` / args）：当设为 `"0"` 或 `0` 时，init 模板不会渲染任何与 `org_id` 相关的内容。
- **效果**：`variable "gcp_common"` 中不包含 `org_id` 字段与 default；`google_project` 等资源中不包含 `org_id` 行。适用于无 Organization 或仅用 Billing Account 的场景。
- **参数**：在 `terraform/args.yaml`、`terraform/init/args.yaml` 中已将 OrganizationID 设为可选，默认 `"0"`。

## 避免重复 output 与 locals

- **Gateway IP 等输出**：仅通过 **ip** 组件的 `output_addresses` 输出；**outputs** 组件不再包含 `gateway_ips`，避免与 ip.tf 重复。
- **vpc_name**：仅在 **main.tf** 中通过 `locals { vpc_name = google_compute_network.main.name }` 定义；**vpc.tf** 不再定义 locals，网络名直接使用参数 `vpc_name`。
