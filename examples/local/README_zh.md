# 本地体验：在笔记本上跑一遍平台层和 GitOps

English: [README.md](./README.md)

不需要 GCP、域名，也不花钱。用本机的 Kubernetes（kind、minikube 或 Docker Desktop）体验 [0→1 指南](../../docs/GETTING_STARTED_zh.md) 里的**第 3 层（平台组件）**和**第 4 层（业务应用）**：

- 平台组件：外部密钥同步（External Secrets 控制器）、加密密钥（Sealed Secrets）、ArgoCD、指标监控（VictoriaMetrics，含存储和告警）、Grafana
- GitOps：把应用写进 Git 仓库，ArgoCD 自动部署到集群

第 1、2 层（GCP 项目、网络、GKE、DNS、证书）需要真实云账号，本地跳过。体验完再按指南上云，用的是同一套组件和同一套 blcli 流程。

整个过程大约 20–40 分钟，大部分时间在拉镜像。

## 0. 准备

- Docker，以及 [kind](https://kind.sigs.k8s.io/) 或 [minikube](https://minikube.sigs.k8s.io/) 之一
- `kubectl`、`helm`、`kustomize`、`curl`、`git`、`ssh-keygen`、`blcli`
- 一个 GitHub 账号
- Docker 至少 4 核 CPU、6 GB **空闲**内存（Docker Desktop 的总内存由所有容器共享，先停掉不用的容器；内存不够时 API Server 会失去响应，安装超时）

## 1. 创建本地集群

```bash
kind create cluster --name bl-local
# 或者：minikube start -p bl-local --cpus 4 --memory 5g
kubectl config current-context     # 确认是 kind-bl-local 或 bl-local，后面的命令都作用在当前 context 上
```

## 2. 准备 gitops 仓库，生成配置

1. 在 GitHub 上新建一个**空仓库**（私有也可以），例如 `<你>/gitops`。
2. 复制参数文件，把里面的两个 `git@github.com:example-org/gitops.git` 改成你的仓库地址：
   ```bash
   cp <bl-template>/examples/local/args.yaml ./args.yaml
   ```
3. 生成 Kubernetes 和 GitOps 配置：
   ```bash
   blcli init <bl-template> -a args.yaml --modules kubernetes --modules gitops -o ./local-workspace
   ```
   `<bl-template>` 可以是本仓库的本地路径，也可以是 `github.com/ggsrc/bl-template`。

生成的内容：

| 目录 | 是什么 |
|------|--------|
| `local-workspace/kubernetes/local/<组件>/` | 每个平台组件的安装文件，数字前缀是安装顺序 |
| `local-workspace/gitops/local/hello-world/` | 示例应用的 Deployment、Service 等，以及给 ArgoCD 的 `app.yaml` |
| `local-workspace/keys/argocd_github(.pub)` | ArgoCD 读仓库用的 SSH 密钥（不要提交到 Git） |

## 3. 给仓库加只读 Deploy Key

```bash
cat local-workspace/keys/argocd_github.pub
```

把输出加到 GitHub 仓库的 **Settings → Deploy keys → Add deploy key**，不要勾选 "Allow write access"。

## 4. 安装平台组件

```bash
blcli apply kubernetes -d ./local-workspace/kubernetes -r <bl-template>
```

按 `0-` → `2-` → `3-` → `4-` 的顺序安装。

**✅ 检查点**

```bash
kubectl get pods -A | grep -v kube-system      # 全部 Running / Completed
kubectl -n monitoring-vm get vmsingle,vmagent,vmalert
```

## 5. 把应用推到 gitops 仓库，交给 ArgoCD

```bash
cd local-workspace/gitops
git init -b main && git add . && git commit -m "hello-world"
git remote add origin git@github.com:<你>/gitops.git && git push -u origin main
cd ../..
blcli apply gitops -d ./local-workspace/gitops --args args.yaml --skip-sync
```

这一步就是 GitOps 的核心：你只改 Git，ArgoCD 负责让集群和 Git 保持一致。

**✅ 检查点**

```bash
kubectl -n argocd get applications              # hello-world 变为 Synced + Healthy（可能要一两分钟）
kubectl -n app port-forward svc/hello-world 8081:8080 &
curl localhost:8081                             # Hello from hello-world
```

## 6. 看看各个界面

| 界面 | 打开方式 | 登录 |
|------|----------|------|
| ArgoCD | `kubectl -n argocd port-forward svc/argocd-server 8080:443`，打开 https://localhost:8080 | 用户 `admin`，密码：`kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath='{.data.password}' \| base64 -d` |
| Grafana | `kubectl -n grafana port-forward svc/grafana 3000:80`，打开 http://localhost:3000 | 用户 `admin`，密码：`kubectl -n grafana get secret grafana -o jsonpath='{.data.admin-password}' \| base64 -d` |
| VictoriaMetrics | `kubectl -n monitoring-vm port-forward svc/vmsingle-victoriametrics-vmks 8429` ，打开 http://localhost:8429/vmui | 无 |

## 7. 动手改一改

- **发布新版本**：把 `gitops/local/hello-world/deployment.yaml` 里的 `-text=...` 改掉，提交并推送。ArgoCD 几分钟内自动同步（或在界面上点 Sync），`curl` 看到新文字。
- **回滚**：`git revert HEAD && git push`，应用回到上一个版本。
- **看监控**：在 Grafana 的 Explore 里选 `victoria-metrics` 数据源，查询 `up` 或 `container_memory_working_set_bytes`。

## 常见问题

| 现象 | 原因与处理 |
|------|------------|
| 报 `open .../helm/repository/<某个仓库>-index.yaml: no such file or directory` | 安装脚本的 `helm dependency update` 会刷新你本机所有的 Helm 仓库，其中某个无关仓库的缓存坏了。执行 `helm repo update`，或用 `helm repo remove <仓库名>` 删掉它，再重新执行第 4 步 |
| 某个组件失败，后面的组件报 `no matches for kind ...` / `ensure CRDs are installed first` | 后面的组件依赖前面组件装的 CRD。先修好第一个失败的组件，再重新执行第 4 步；已装好的组件重复执行不会有问题 |
| 安装报 `context deadline exceeded` / `TLS handshake timeout` | 多半是内存不够，集群 API Server 卡住。用 `docker stats` 看是否有别的容器占用内存，腾出内存后重新执行第 4 步 |
| Pod 长时间 `ContainerCreating` / `Pending` | 首次拉镜像较慢，`kubectl get pods -A -w` 观察；如果是 `Pending`，`kubectl describe pod` 多半是内存不够，给 Docker / minikube 多分配些 |
| Application 显示认证失败 | Deploy Key 没加，或加到了别的仓库；`args.yaml` 里两处仓库地址要和实际仓库一致 |

## 8. 清理

```bash
kind delete cluster --name bl-local     # 或 minikube delete -p bl-local
```

GitHub 上的 gitops 仓库和 Deploy Key 需要自己删除。

## 和上云的区别

| | 本地 | GCP（[0→1 指南](../../docs/GETTING_STARTED_zh.md)） |
|---|---|---|
| 第 1、2 层 | 跳过 | Terraform 创建项目、网络、GKE、DNS、证书 |
| 密钥 | 只装 External Secrets 控制器，没有可读的密钥库 | 另装 `external-secrets`，通过 Workload Identity 读 GCP Secret Manager |
| 告警 | 规则照常计算，不发 Slack | 配好 Secret Manager 里的 Slack webhook 后发到 Slack |
| 规格 | 存储 5Gi、保留 7 天 | 存储 20Gi、保留 30 天 |
