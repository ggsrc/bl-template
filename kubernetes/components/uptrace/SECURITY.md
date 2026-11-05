# Uptrace security and migration

The dependency is official Uptrace chart 2.0.1 with local, readable security
patches (UPSTREAM.md). Application settings have two `uptrace` levels in wrapper
values; chart-level settings such as Ingress have one. The application stays on
2.0.1: fixing the old ignored `1.7.0` override must not downgrade an existing DB.

## First installation

Install CloudNativePG and the Altinity ClickHouse operator/CRDs first. This wrapper
does not install the Altinity operator. Its namespace defaults to
`clickhouse-operator` in `networkPolicy.clickhouseOperatorIngress`; adjust to your
operator's actual namespace. The chart's Postgres and ClickHouse objects retain
their upstream fixed names, so use **one release per dedicated namespace**.

Helm creates `<release>-bootstrap`, retaining it on uninstall and reusing it via
`lookup` on upgrade. Its independent random keys are `admin-password`,
`service-secret`, `user-token`, `project-token`, and `clickhouse-password`.
Config is a Secret. ClickHouse uses the corresponding password hash; the application
reads the same password through SecretKeyRef. CNPG generates the PostgreSQL role.
Restrict access to Secrets and Helm release records, which contain the credentials.

No Ingress or bundled OpenTelemetry collector/host-network DaemonSet is created.
NetworkPolicy defaults to no application ingress. Bootstrap over port-forward,
using `admin@uptrace.local` and the bootstrap password. Then allow only trusted
gateway/collector peers. Put the actual Pod CIDR in `clickhouseAllowedCIDR`
(default `10.0.0.0/8`); do not set it to `::/0` or `0.0.0.0/0`.

Configure your existing collector with the new project token from the bootstrap
Secret using SecretKeyRef/your secret manager. Its OTLP exporter needs an
`uptrace-dsn` header using that token, the actual Uptrace service hostname, HTTP
port 80, and gRPC port 4317. Allow the collector's namespace and Pod selector to
port 4317 (or HTTP ingestion on port 80) in `networkPolicy.ingress`. The generic
otel-collector component does not automatically read a Secret in another namespace;
replicate it through your secret manager instead of committing the DSN.

Validate a trace/log write and query it back before accepting the installation.
ClickHouse egress is also restricted to DNS; add narrowly scoped
`networkPolicy.clickhouseEgress` only for reviewed external data sources or peers.
Allow notification/SMTP/OIDC egress only as needed; NodeLocal DNS needs an extra
DNS egress rule. Verify NetworkPolicy enforcement in the target CNI.

## Existing installations

1. Close the old public route. Back up and restore-test PostgreSQL, ClickHouse,
   values, Secrets and operator custom resources. Record data and schema versions.
2. Rotate the actual Uptrace admin password and user/project tokens through its
   supported application/API. Updating `seed_data` does not reliably update existing
   users/tokens. Coordinate new project tokens with every telemetry producer.
3. Rotate ClickHouse's real password, update both its password hash and application
   connection, and preserve PostgreSQL's CNPG-generated app Secret. Set a new service
   secret and plan for session invalidation; test token/session behavior.
4. Create a Helm-owned `<release>-bootstrap` with the migrated values (random
   alphanumeric, >=32 characters). Include Helm managed-by label and release-name /
   release-namespace annotations. A missing bootstrap Secret blocks upgrades.
5. Render into a fresh output directory and review the diff, including the correct
   two-level image override, removal of old Ingress/collectors, and policies. Run the
   installer with `BLCLI_SECURITY_MIGRATION_APPROVED=1` only after the migration rehearsal.
6. Confirm old credentials fail, new login works, trace/log ingest and queries work,
   and operator reconciliation is healthy. Verify there is no external load balancer.

Use Helm against the target cluster for upgrades; offline `helm template` cannot
look up retained credentials and produces fresh preview values. Do not apply those
previews or rotate only the Secret while leaving database credentials unchanged.
