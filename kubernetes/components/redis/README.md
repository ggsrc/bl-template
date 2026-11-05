# Redis

Shared Redis deployment based on the Bitnami Redis Helm chart.

## Features

- Standalone mode with AOF persistence
- Password injected through an ExternalSecret (`auth.existingSecret`)
- Optional GCP internal load balancer (`enable-internal-lb`)
- Dangerous commands disabled (see below)

## Disabled commands

The template renames these commands to `""` on master and replicas, so clients cannot run them:

- `FLUSHDB`, `FLUSHALL` (chart default)
- `CONFIG`, `DEBUG`, `MODULE`, `SLAVEOF`, `REPLICAOF`: server reconfiguration, file writes and native code loading
- `EVAL`, `EVALSHA`, `EVAL_RO`, `EVALSHA_RO`, `FUNCTION`, `FCALL`, `FCALL_RO`, `SCRIPT`: Lua scripting and functions. This blocks CVE-2025-49844 (Lua use-after-free, remote code execution for any authenticated client) and other Lua engine bugs in the pinned image.

Notes:

- Clients that need Lua (for example BullMQ or redlock) fail with `ERR unknown command`. To keep scripting, set `allowLuaScripting: true` for this component, and use a Redis image patched for CVE-2025-49844 (7.2.11, 7.4.6, 8.0.4, 8.2.2 or later).
- With `CONFIG` disabled the metrics exporter no longer reports `redis_config_*` metrics; other metrics are unaffected.
- Sentinel mode needs `CONFIG` and `REPLICAOF`. Remove them from `disableCommands` in `values-override.yaml` if you enable Sentinel.
- `rename-command` fails at startup for commands the server does not know; `EVAL_RO`, `EVALSHA_RO`, `FUNCTION`, `FCALL` and `FCALL_RO` need Redis 7.0 or later.

## Install

```bash
bash ./install
```

## Prerequisites

- Store the Redis password in GCP Secret Manager
- Sync it into the `redis-shared` Secret (key `REDIS_PASSWORD`) with the `external-secrets` component
- The install script labels the namespace `gcp-secret-store-access=allowed`, so an ExternalSecret there can use the `gcp-secret-store` ClusterSecretStore
