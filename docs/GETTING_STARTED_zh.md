# 从 0 到 1 搭建 Infra

English version: [GETTING_STARTED.md](./GETTING_STARTED.md)

这份文档写给**创业团队和个人开发者**：你可能没有专职的 SRE，但希望从第一天起就有一套"能长大"的基础设施。我们不只告诉你执行哪条命令，更想讲清楚**每一层是什么、为什么需要、在模板里对应哪个目录**，让你真正理解自己的 infra，而不是拿到一堆看不懂的 YAML。

---

## 全局视图：一套 infra 由哪几层组成

```
┌───────────────────────────────────────────────────────────────┐
│ 第 4 层  业务应用         gitops/          ArgoCD Application   │
├───────────────────────────────────────────────────────────────┤
│ 第 3 层  平台组件         kubernetes/      密钥 / 网关 / GitOps / 监控 │
├───────────────────────────────────────────────────────────────┤
│ 第 2 层  环境资源         terraform/project/  VPC / GKE / DNS / 证书 │
├───────────────────────────────────────────────────────────────┤
│ 第 1 层  云账号地基       terraform/init/  State 存储 / GCP 项目   │
└───────────────────────────────────────────────────────────────┘
          blcli：init-args → init → apply → status → rollback
```

下层是上层的前提，所以搭建顺序**永远是从下往上**。blcli 根据各 `config.yaml` 里的 `dependencies` 帮你保证顺序。

| 层 | 解决什么问题 | 不做会怎样 |
|----|--------------|------------|
| 云账号地基 | 资源归属、计费、Terraform 状态存在哪 | 多人改 infra 会互相覆盖，资源散落各处 |
| 环境资源 | 网络、集群、域名、证书 | 只能手点控制台，无法复现、无法审计 |
| 平台组件 | 密钥、流量入口、发布、可观测 | 每个业务各自造轮子，出问题看不到 |
| 业务应用 | 应用如何声明式地部署 | 部署靠 `kubectl apply` 手敲，回滚靠记忆 |

---

## 阶段 0：准备工作

**你需要：**

- 一个 GCP 账号和 Billing Account（**不需要** GCP Organization——把 `OrganizationID` 设为 `"0"` 即可，见 [terraform/TERRAFORM_PROJECT_zh.md](../terraform/TERRAFORM_PROJECT_zh.md)）
- 一个域名（可以之后再买，但证书和对外访问都依赖它）
- 一个 GitHub 组织或账号，用来存放生成的 terraform / kubernetes / gitops 仓库
- 本地工具：`blcli`、`terraform`、`gcloud`、`kubectl`、`helm`、`gh`

**生成参数文件：**

```bash
blcli init-args -r github.com/ggsrc/bl-template -o args.yaml
```

`args.yaml` 是你整套 infra 的"唯一事实来源"。每个参数在模板的 `args.yaml` 里都有描述和示例，看不懂某个参数时用 `blcli explain` 查询（例如 `blcli explain -r github.com/ggsrc/bl-template -m kubernetes -c argocd`），设计细节见 [ARGS_DESIGN.md](../ARGS_DESIGN.md)。

> **小团队建议：先从一个环境开始。** 模板默认生成 `corp / stg / prd` 三个项目，这是团队规模变大后的形态。起步时可以在 `args.yaml` 里只保留 `prd`（或 `stg` + `prd`），之后再按同样的方式加环境——这正是模板化的意义。

---

## 阶段 1：云账号地基（`terraform/init/`）

**是什么：** 在写任何业务资源之前，先解决两件事——Terraform 的状态（state）存在哪里，以及资源属于哪个 GCP 项目。

| 生成目录 | 作用 |
|----------|------|
| `terraform/init/0-terraform-statestore/` | 创建存 Terraform state 的 GCS bucket（`prepare: true`，最先执行） |
| `terraform/init/1-<GlobalName>-projects/` | 创建 GCP 项目并开启所需 API |
| `terraform/init/2-atlantis/` | （可选）Atlantis 服务账号，用于"PR 驱动的 Terraform" |

**为什么：** 远程 state 让多人协作时不会互相覆盖；一个环境一个 GCP 项目，权限、账单和故障都天然隔离。

**小团队建议：** Atlantis 可以晚点再上。一两个人维护 infra 时，本地 `terraform apply` + 代码评审已经够用。

---

## 阶段 2：环境资源（`terraform/project/`）

**是什么：** 每个环境的网络、Kubernetes 集群、域名和证书。

推荐的引入顺序（也是依赖顺序）：

1. **`main` / `provider` / `variables` / `backend`** — 每个 Terraform 项目的骨架
2. **`vpc`** — 私有网络，集群和数据库都放在里面
3. **`gke`** — Kubernetes 集群（模板里带 on-demand + spot 两种节点池，spot 节点能显著省钱）
4. **`ip` / `firewall`** — 对外入口的静态 IP 与防火墙规则
5. **`dns` / `cert`** — 域名解析与 HTTPS 证书
6. **`artifacts-registry`** — 存放你的容器镜像
7. 按需：`iam`、`cdn`、`vpc-peering`、`loki-logs`

每个组件选什么、为什么，见 [terraform/TERRAFORM_PROJECT_zh.md](../terraform/TERRAFORM_PROJECT_zh.md)。

**小团队建议：** 单环境起步只需要 `main, backend, provider, variables, vpc, gke, ip, dns, cert, artifacts-registry`。`vpc-peering` 只有在多个环境要互通（例如共用的 corp 集群）时才需要。

---

## 阶段 3：平台组件（`kubernetes/`）

**是什么：** 集群起来之后、业务上线之前，要先装一层"平台"。`kubernetes/default.yaml` 是默认核心栈，数字前缀就是安装顺序：

| 顺序 | 组件 | 它解决的问题 |
|------|------|--------------|
| 0 | `external-secrets-operator` + `external-secrets` | 从 GCP Secret Manager 同步密钥进集群，密码不进 Git |
| 0 | `sealed-secret` | 必须放进 Git 的密钥先加密再提交 |
| 1 | `istio` | 统一流量入口、mTLS、灰度路由 |
| 2 | `argocd` | GitOps：Git 里是什么，集群里就是什么 |
| 3–4 | `victoria-metrics-operator` + `victoria-metrics` | 指标采集与告警 |
| corp | `grafana` | 看板 |

可选组件（数据库、缓存、消息队列、日志、APM 等）见 [kubernetes/OPTIONAL_COMPONENTS.md](../kubernetes/OPTIONAL_COMPONENTS.md)，需要时在 `args.yaml` 中加上即可。

**小团队建议：**

- **一定要装：** 密钥管理（external-secrets）、ArgoCD、指标监控。这三样越晚补越痛。
- **可以晚点：** Istio。只有一两个服务时，GKE 自带的 Ingress / Gateway 已经够用；服务变多、需要 mTLS 或灰度时再加。
- **数据库：** 早期优先用托管服务（Cloud SQL）；需要在集群内跑 Postgres 时再启用 `cnpg`。

---

## 阶段 4：业务应用（`gitops/`）

**是什么：** 把你的应用描述成 Deployment / StatefulSet + Service + ConfigMap，并生成 ArgoCD Application，由 ArgoCD 自动同步到集群。

`gitops/default.yaml` 带了一个 `hello-world` 示例。把它换成你自己的应用：名字、镜像、端口、健康检查。

```bash
blcli apply gitops -d ./workspace/output/gitops --args args.yaml
```

**为什么：** 之后每次发布都只是一次 Git 提交；回滚就是 `git revert`。谁在什么时间改了什么，全部有记录。

---

## 阶段 5：生成、推送、部署

```bash
# 1. 根据 args.yaml 渲染全部配置
blcli init -r github.com/ggsrc/bl-template -a args.yaml --output ./workspace/output

# 2. 把生成的 terraform / kubernetes / gitops 推到 GitHub
blcli apply init-repos -o <your-github-org> -d ./workspace/output

# 3. 按层部署（先加 --dry-run 看计划）
blcli apply terraform  -d ./workspace/output/terraform --dry-run
blcli apply terraform  -d ./workspace/output/terraform
blcli apply kubernetes -d ./workspace/output/kubernetes -r github.com/ggsrc/bl-template
blcli apply gitops     -d ./workspace/output/gitops --args args.yaml
# 或者一键：blcli apply all -d ./workspace/output --args args.yaml

# 4. 检查状态
blcli status --args args.yaml
```

部署出错时，`blcli rollback` 可以回退（例如 `blcli rollback terraform --args args.yaml --dry-run` 先预览）。

---

## 理解之后：改造成你自己的模板

本仓库的定位是**可以 fork 的参考实现**。理解了上面四层之后，你可以：

- 在 `terraform/project/` 中新增资源模板，并在 `terraform/config.yaml` 注册
- 在 `kubernetes/components/` 中新增组件，并在 `kubernetes/config.yaml` 注册与声明依赖
- 修改各级 `args.yaml`，让参数描述贴合你团队的习惯

blcli 本身不需要改动。

---

## 常见问题

**我只有一个人，用这个会不会太重？**
可以从单环境、核心组件开始，按上面的"小团队建议"裁剪。如果你只想要最轻量的形态，也可以先看 [bl-template-personal](https://github.com/ggsrc/bl-template-personal)，等团队长大后再迁移到本模板——两者使用同一套 blcli 协议。

**没有 GCP Organization 能用吗？**
可以。`OrganizationID` 设为 `"0"`，只用 Billing Account 即可。

**大概要花多少钱？**
主要成本来自 GKE 节点和负载均衡。单环境 + spot 节点池是最省钱的起步方式；具体以 GCP 定价为准。
