# Redis

Shared Redis deployment based on the Bitnami Redis Helm chart.

## Features

- Standalone mode with AOF persistence
- Password injected through an ExternalSecret (`auth.existingSecret`)
- Optional GCP internal load balancer (`enable-internal-lb`)

## Install

```bash
bash ./install
```

## Prerequisites

- Store the Redis password in GCP Secret Manager
- Sync it into the `redis-shared` Secret (key `REDIS_PASSWORD`) with the `external-secrets` component
