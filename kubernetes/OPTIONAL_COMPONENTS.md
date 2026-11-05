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
| redis | Bitnami Chart → `bitnami/redis` | external-secrets | Shared Redis |
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
