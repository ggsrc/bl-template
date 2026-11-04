# CloudNativePG Operator

CloudNativePG is an operator for running PostgreSQL clusters on Kubernetes.

Based on the upstream CloudNativePG Helm chart (`https://cloudnative-pg.github.io/charts`).

## Install

After rendering with blcli, run in the component directory:

```bash
bash ./install
```

Or manually:

```bash
helm dependency update
helm upgrade --install cloudnative-pg . -n cnpg --create-namespace \
  -f values.yaml -f values-override.yaml --wait
```

## Create a PostgreSQL cluster

After installing the operator, create database clusters with the `postgresql.cnpg.io/v1` `Cluster` CR. Cluster definitions usually live in your GitOps repository.
