# Redis (Valkey)

Shared Redis-compatible cache based on the official [Valkey Helm chart](https://github.com/valkey-io/valkey-helm)
(`valkey` 0.12.1, image `valkey/valkey:9.1.3`). The component keeps the name `redis` so existing args files keep working.

## Features

- Standalone mode, AOF on, RDB snapshots off, data in an emptyDir (lost on restart)
- ACL authentication always on; the password comes from an ExternalSecret (`existingSecret`, key `existingSecretPasswordKey`)
- Dangerous commands and Lua scripting denied through ACL categories (see below)
- Metrics exporter sidecar (`oliver006/redis_exporter`) logging in as a read-only `metrics` user
- In-cluster address unchanged from the previous Bitnami chart: `<release>-master.<namespace>.svc:6379` (default `redis-master.redis.svc:6379`)
- Optional GCP internal load balancer, off by default and limited to `internalLBSourceRanges`

## ACL users

Both users read their password from the same Secret key.

| User | Permissions |
|------|-------------|
| `default` | `~* &* +@all -@dangerous +info -@scripting` |
| `metrics` | `-@all` plus `PING`, `INFO`, `SELECT`, `CLIENT SETNAME/LIST`, `SLOWLOG GET/LEN`, `LATENCY LATEST/HISTOGRAM`, `COMMANDLOG GET/LEN`, `MEMORY STATS` |

`@dangerous` includes `CONFIG`, `DEBUG`, `MODULE`, `REPLICAOF`/`SLAVEOF`, `FLUSHALL`, `FLUSHDB`, `KEYS`, `SORT`, `MONITOR`,
`SHUTDOWN`, `SAVE`/`BGSAVE`, `MIGRATE`, `RESTORE`, `CLIENT LIST`/`KILL`, `ACL` write commands and similar. `INFO` is added back
because client libraries (for example ioredis and BullMQ) call it. Denied commands fail with `NOPERM`.

Parameters:

- `allowLuaScripting: true` drops `-@scripting`, for clients that need Lua (for example BullMQ or redlock).
  Valkey 9.1.3 is not affected by CVE-2025-49844.
- `extraAclRules` is appended to the default user's rules, for example `+keys +sort`.

The exporter cannot read `CONFIG`, so `redis_config_*` metrics are not reported.

## Internal load balancer

`enableInternalLB: true` adds a GCP internal `LoadBalancer` Service (`internalLBServiceName`, default `redis-shared-lb`).
`internalLBSourceRanges` (comma-separated CIDRs) is required; the install fails without it.

## Install

```bash
bash ./install
```

The script downloads the chart version pinned in `Chart.lock` with `helm pull --repo` (no `helm repo add` needed) and checks its sha256.

## Prerequisites

- Store the password in GCP Secret Manager
- Sync it into the `redis-shared` Secret (key `REDIS_PASSWORD`) with the `external-secrets` component
- The install script labels the namespace `gcp-secret-store-access=allowed`, so an ExternalSecret there can use the `gcp-secret-store` ClusterSecretStore
