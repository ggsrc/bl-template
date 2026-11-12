# 从 0 到 1 搭建 Infra

English version: [GETTING_STARTED.md](./GETTING_STARTED.md)

这份文档写给**创业团队和个人开发者**：你可能没有专职的 SRE，但希望从第一天起就有一套"能长大"的基础设施。我们不只告诉你执行哪条命令，更想讲清楚**每一层是什么、为什么需要、在模板里对应哪个目录**，让你真正理解自己的 infra，而不是拿到一堆看不懂的 YAML。

> **想先零成本体验？** [examples/local/](../examples/local/README_zh.md) 用本机的 kind 或 minikube 跑第 3、4 层（平台组件 + GitOps），不需要 GCP 和域名，大约 30 分钟。

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
- 本地工具：`blcli`、`terraform`、`gcloud`、`kubectl`、`helm`、`gh`，以及 ArgoCD 安装脚本要用的 `kustomize`、`curl`
- `gcloud auth login` 和 `gcloud auth application-default login`（Terraform 用后者的凭据）

**动手前先准备好这几样：**

| 准备什么 | 给谁用 | 不准备会怎样 |
|----------|--------|--------------|
| 一个 gitops 仓库（GitHub 上新建一个空仓库即可），把它的 SSH 地址 `git@github.com:<你>/<仓库>.git` 填到 argocd 的 `GitRepositoryURL` 和 gitops 应用的 `SourceRepoURL` | ArgoCD 从这里同步应用 | ArgoCD 找不到仓库，应用无法同步 |
| 仓库的只读 Deploy Key：安装 argocd 时脚本会生成 `<workspace>/keys/argocd_github.pub`，把它加到仓库 Settings → Deploy keys（不要勾选写权限） | ArgoCD 读取私有仓库 | 同步报认证失败 |
| Secret Manager 中的 `slack-webhook-url-infra-alert`（一个 Slack Incoming Webhook URL） | 告警发到 Slack | 告警规则照常计算，但 Alertmanager 拿不到 webhook，告警发不出去 |

ArgoCD 默认用内置 admin 账号登录，不需要配置 GitHub 登录。团队变大后可以换成 GitHub App + GitHub 登录（Dex）+ 按组织分权限，配置见 [examples/multi-env/](../examples/multi-env/)。

**生成参数文件：**

```bash
blcli init-args -r github.com/ggsrc/bl-template -o args.yaml
```

`args.yaml` 是你整套 infra 的"唯一事实来源"。注意 `init-args` 还会在旁边生成一个 `.env`，里面的值（例如 `BLCLI_ARGOCD_GIT_REPOSITORY_URL`）会在 `blcli init` 时覆盖 `args.yaml` 的对应字段，并作用于所有环境；改仓库地址时两边要一起改，或者直接删掉 `.env` 里不需要的行。每个参数在模板的 `args.yaml` 里都有描述和示例，看不懂某个参数时用 `blcli explain` 查询（例如 `blcli explain -r github.com/ggsrc/bl-template -m kubernetes -c argocd`），设计细节见 [ARGS_DESIGN.md](../ARGS_DESIGN.md)。

> **默认只有一个环境。** 模板默认只生成一个 `prd` 项目：一个 GCP 项目、一个 GKE 集群、一套平台组件，监控也在同一集群内闭环。团队变大、需要 `stg` / `prd` / 共享的 `corp` 时，参考 [examples/multi-env/](../examples/multi-env/) 按同样的方式加环境——这正是模板化的意义。

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

**✅ 检查点**

```bash
gcloud projects list                   # 能看到 <GlobalName>-tfstore-xxxx 和 <GlobalName>-prd-xxxx
gcloud storage ls --project <GlobalName>-tfstore-xxxx   # 能看到存 state 的 bucket
# 在 terraform/init/1-<GlobalName>-projects/ 目录下：
terraform output project_ids           # prd 对应的真实项目 ID，后面各阶段都会用到
```

项目 ID 带随机后缀（GCP 项目 ID 全局唯一），blcli 会把 args 里的 `prd` 自动换成真实 ID，不需要手动改。

**常见问题**

| 现象 | 原因与处理 |
|------|------------|
| 创建项目报 billing 相关错误 | `BillingAccountID` 不对，或这个 Billing Account 关联的项目数已达上限（默认很少），在控制台申请提额 |
| 报 `SERVICE_DISABLED` / API 未启用 | 刚开启的 API 需要几分钟生效，稍等后重新 apply |

---

## 阶段 2：环境资源（`terraform/project/`）

**是什么：** 每个环境的网络、Kubernetes 集群、域名和证书。

推荐的引入顺序（也是依赖顺序）：

1. **`main` / `provider` / `variables` / `backend`** — 每个 Terraform 项目的骨架
2. **`vpc`** — 私有网络，集群和数据库都放在里面
3. **`gke`** — Kubernetes 集群。主节点池（1–3 台 e2-standard-2，自动扩缩）跑平台组件；另有 on-demand 和 spot 两个带污点的节点池（e2-standard-4，可缩到 0），应用加上对应的 toleration 才会调度过去。spot 节点能显著省钱
4. **`ip` / `firewall`** — 对外入口的静态 IP 与防火墙规则
5. **`dns` / `cert`** — 域名解析与 HTTPS 证书
6. **`artifacts-registry`** — 存放你的容器镜像
7. 按需：`iam`、`cdn`、`vpc-peering`、`loki-logs`

每个组件选什么、为什么，见 [terraform/TERRAFORM_PROJECT_zh.md](../terraform/TERRAFORM_PROJECT_zh.md)。

**默认组件：** `main, backend, config-gcs-tfbackend, provider, variables, vpc, ip, gke, dns, cert, artifacts-registry, outputs`——这就是单环境起步所需的全部。`firewall`、`iam`、`cdn`、`loki-logs` 按需添加；`vpc-peering` 只有在多个环境要互通（例如共用的 corp 集群）时才需要。

**✅ 检查点**

```bash
gcloud container clusters get-credentials prd-cluster --region us-west1 --project <prd 项目 ID>
kubectl get nodes                      # 1 个 Ready 节点（e2-standard-2）；两个应用节点池此时为 0 个节点是正常的
gcloud dns managed-zones list --project <prd 项目 ID>    # 公网 zone 的 dns_name 是你的域名
gcloud certificate-manager certificates list --project <prd 项目 ID>   # 证书最终应为 ACTIVE
```

**常见问题**

| 现象 | 原因与处理 |
|------|------------|
| 证书一直是 `PROVISIONING` | 域名还没委派给 Cloud DNS。用 `gcloud dns managed-zones describe <zone> --format='value(nameServers)'` 取出 NS 记录，到域名注册商那里把该域名（或子域名）的 NS 指过去；生效后证书通常几十分钟内变为 ACTIVE |
| 报配额不足（`CPUS`、`IN_USE_ADDRESSES` 等） | 新项目配额很低，在控制台 IAM & Admin → Quotas 申请提额 |
| `terraform destroy` 删不掉集群 | `deletionProtection: true` 是故意的，防止误删；确实要删时先改成 false 再 apply |

---

## 阶段 3：平台组件（`kubernetes/`）

**是什么：** 集群起来之后、业务上线之前，要先装一层"平台"。`kubernetes/default.yaml` 是默认核心栈（单环境 `prd`），数字前缀就是安装顺序：

| 顺序 | 组件 | 它解决的问题 |
|------|------|--------------|
| 0 | `external-secrets-operator` + `external-secrets` | 从 GCP Secret Manager 同步密钥进集群，密码不进 Git |
| 0 | `sealed-secret` | 必须放进 Git 的密钥先加密再提交 |
| 2 | `argocd` | GitOps：Git 里是什么，集群里就是什么 |
| 3–4 | `victoria-metrics-operator` + `victoria-metrics` | 指标采集、存储（VMSingle）与告警，全部在本集群内 |
| 4 | `grafana` | 看板（默认用 admin 账号密码登录，不需要 Google Workspace） |

可选组件（数据库、缓存、消息队列、日志、APM 等）见 [kubernetes/OPTIONAL_COMPONENTS.md](../kubernetes/OPTIONAL_COMPONENTS.md)，需要时在 `args.yaml` 中加上即可。

**小团队建议：**

- **一定要装：** 密钥管理（external-secrets）、ArgoCD、指标监控。这三样越晚补越痛。
- **Grafana 登录：** 默认 `auth-mode: password`，用 admin 账号登录：`kubectl -n grafana port-forward svc/grafana 3000:80` 后打开 http://localhost:3000，密码用 `kubectl -n grafana get secret grafana -o jsonpath='{.data.admin-password}' | base64 -d` 取得。团队用 Google Workspace 时可改为 `auth-mode: google`。
- **默认不装：** Istio。只有一两个服务时，GKE 自带的 Ingress / Gateway 已经够用；服务变多、需要 mTLS 或灰度时，在 `args.yaml` 中加上 `istio` 组件，并给 gitops 应用设置 `VirtualServiceEnabled: true`。
- **监控存储：** 默认 `storage-mode: local`，指标存在本集群的 VMSingle 里。多环境时可以改为 `remote`，把各集群的指标汇总到一个中心集群（见 [examples/multi-env/](../examples/multi-env/)）。
- **数据库：** 早期优先用托管服务（Cloud SQL）；需要在集群内跑 Postgres 时再启用 `cnpg`。

**✅ 检查点**

```bash
kubectl get pods -n external-secrets; kubectl get pods -n sealed-secret
kubectl get pods -n argocd; kubectl get pods -n monitoring-vm; kubectl get pods -n grafana
                                       # 全部 Running / Completed
kubectl get clustersecretstore gcp-secret-store         # READY 为 True：集群能读 Secret Manager 了
kubectl -n monitoring-vm get vmsingle,vmagent,vmalert   # 状态均为 operational
kubectl -n grafana port-forward svc/grafana 3000:80     # 打开 http://localhost:3000，用 admin 登录
kubectl -n argocd port-forward svc/argocd-server 8080:443   # 打开 https://localhost:8080，用 admin 登录
kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath='{.data.password}' | base64 -d   # admin 密码
```

**常见问题**

| 现象 | 原因与处理 |
|------|------------|
| `gcp-secret-store` 不是 Ready | Workload Identity 没对上：组件参数 `ClusterName` 必须和 Terraform 里的 GKE 集群名一致（默认都是 `prd-cluster`）；再确认阶段 2 已创建 `sa-sm-accessor` |
| ExternalSecret 显示 `SecretSyncedError` | Secret Manager 里还没有对应的 secret（例如 `slack-webhook-url-infra-alert`），创建后等下一次同步 |
| Pod 一直 `Pending` | 节点资源不够，`kubectl describe pod` 看原因；主节点池会自动扩到 3 台，仍不够就调大 `machineType` |
| ArgoCD 安装脚本报 `is an https URL` | 默认用 SSH Deploy Key，仓库地址必须是 `git@github.com:...` 形式，不能是 https |

---

## 阶段 4：业务应用（`gitops/`）

**是什么：** 把你的应用描述成 Deployment / StatefulSet + Service + ConfigMap，并生成 ArgoCD Application，由 ArgoCD 自动同步到集群。

`gitops/default.yaml` 带了一个 `hello-world` 示例。把它换成你自己的应用：名字、镜像、端口、健康检查。

```bash
blcli apply gitops -d ./workspace/output/gitops --args args.yaml
```

**为什么：** 之后每次发布都只是一次 Git 提交；回滚就是 `git revert`。谁在什么时间改了什么，全部有记录。

**✅ 检查点**

```bash
kubectl -n argocd get applications     # hello-world 为 Synced + Healthy
kubectl -n app get pods                # 应用 Pod 为 Running
```

**常见问题**

| 现象 | 原因与处理 |
|------|------------|
| Application 报 `repository not found` / `ComparisonError` / 认证失败 | `SourceRepoURL` 和 `GitRepositoryURL` 还是示例的 `example-org/gitops`，改成你自己的仓库（两处要一致，`.env` 里也要改）；并确认 `argocd_github.pub` 已加为该仓库的 Deploy key |
| 同步时报 `no matches for kind "VirtualService"` | 给应用设置了 `VirtualServiceEnabled: true`，但集群没装 Istio；去掉该参数，或先安装 `istio` 组件 |
| 同步时报不允许的仓库或命名空间 | ArgoCD 的 `apps` 项目只允许配置过的 gitops 仓库和应用命名空间，在 argocd 组件参数 `AppProjectSourceRepos` / `AppProjectNamespaces` 中加上 |

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
默认就是单环境 + 核心组件，还可以按上面的"小团队建议"进一步裁剪。如果你只想要最轻量的形态，也可以先看 [bl-template-personal](https://github.com/ggsrc/bl-template-personal)，等团队长大后再迁移到本模板——两者使用同一套 blcli 协议。

**没有 GCP Organization 能用吗？**
可以。`OrganizationID` 设为 `"0"`，只用 Billing Account 即可。

**大概要花多少钱？**
主要成本来自 GKE 节点和负载均衡。默认配置空闲时只有一台 e2-standard-2 节点在跑，两个应用节点池都缩到 0；无状态应用优先放到 spot 节点池最省钱。具体以 GCP 定价为准。
