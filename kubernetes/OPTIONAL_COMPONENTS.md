# Optional Kubernetes Components

The components below are registered in `kubernetes/config.yaml` but are **not enabled** in `kubernetes/default.yaml` by default. `blcli init` renders them only after you add matching entries to `kubernetes.projects[].components[]` in the generated `args.yaml`.

All images are **official upstream images** (no private registry).

## How to enable

```yaml
kubernetes:
  projects:
    - name: stg
      components:
        - name: cnpg
          parameters:
            namespace: cnpg
            release-name: cloudnative-pg
        - name: redis
          parameters:
            namespace: redis
            existing-secret: redis-shared
```

Install: in the rendered output directory, run `bash ./install` (Helm components) or `kubectl apply -k .` (Kustomize components).

## Components

| Component | Official image / chart | Depends on | Description |
|------|------------------|------|------|
| cnpg | `ghcr.io/cloudnative-pg/cloudnative-pg` | — | CloudNativePG Operator |
| redis | Official Valkey chart → `valkey/valkey` | external-secrets | Shared Redis-compatible cache (Valkey) |
| paradedb | Official ParadeDB chart | cnpg | PostgreSQL + search extensions |
| kafka | Bitnami Chart → `bitnami/kafka` | — | Kafka in KRaft mode |
| juicefs | `juicedata/mount` | external-secrets | JuiceFS S3 Gateway (Kustomize) |
| loki | Grafana Community Chart | — | Log aggregation |
| grafana | `grafana/grafana` | victoria-metrics-operator | **Already in the default corp stack**; can also be opted in on its own |
| otel-collector | Official OpenTelemetry chart | — | Log / metric / trace collection |
| uptrace | `uptrace/uptrace` | cnpg | APM (official Helm chart) |
| n9e | `flashcatcloud/nightingale` | victoria-metrics-operator | Nightingale monitoring |
| bytebase | `bytebase/bytebase` | — | Database change management |
| navigation | `b4bz/homer` | — | Internal navigation page (Homer, **bl-template only**) |

## Dependency order

blcli orders components automatically using `dependencies` in `config.yaml`, for example:

- `cnpg` ← paradedb, uptrace
- `external-secrets` ← redis, juicefs
- `victoria-metrics-operator` ← grafana, n9e

## Relationship to default.yaml

| Source | Meaning |
|------|------|
| `config.yaml` | Every component the template repository **can** provide |
| `default.yaml` | The core stack that `init-args` writes to args by default (ESO, Istio, ArgoCD, VM, etc.) |
| Components listed in this file | You must **opt in** to them in args |

For each component's parameters, see `kubernetes/components/<name>/args.yaml` or run `blcli explain -r <repo> -m kubernetes -c <name>`.

## Security-sensitive administration services

Before enabling or upgrading n9e, Uptrace or Bytebase, read their component
`SECURITY.md` files and the repository `SECURITY-CHANGES.md`. They default to private
access and restrictive NetworkPolicy. Complete bootstrap over authorized
port-forward, configure identity/signup restrictions, and then allow trusted
peers. NetworkPolicy requires an enforcing CNI; default policies are not a substitute
for authentication. Uptrace additionally needs an Altinity ClickHouse operator.
Bytebase's default metadata database depends on the CNPG operator.

Run `python scripts/test-security.py` with blcli, Helm 3.18.4 and PyYAML 6.0.3
installed. Tests generate into `workspace/`, use fake kubectl/terraform and a local
fake Kubernetes API with an explicit temporary kubeconfig, and clean up afterward.
They never connect to the caller's current context or cloud accounts.

For explicit local Docker canaries, run
`BLCLI_SECURITY_CONTAINER_TESTS=1 python scripts/test-security-containers.py`.
It rejects remote Docker endpoints, publishes no host ports, uses an internal
network and temporary databases, and removes its containers, anonymous volumes,
network and workspace files. It checks actual n9e login/new-vs-old credentials,
Uptrace config against temporary PostgreSQL/ClickHouse, and Bytebase's non-root,
read-only startup without embedded PostgreSQL. It does not validate a real CNI,
GKE load balancer, production migration, or the complete telemetry/business flow.

The follow-up canary also checks nginx HTTP/TLS proxy login with UID 10000,
dropped capabilities and a read-only root filesystem, plus a synthetic metric
write/query against temporary vmstorage/vminsert/vmselect. Docker uses a private
DNS alias and maps the Kubernetes center Service port 80 to container port 17000;
it does not simulate CNI policy enforcement or run n9e's full alert/notification
lifecycle. The offline test asserts the rendered monitoring namespace/8481 rule.
