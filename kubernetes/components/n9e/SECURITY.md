# Nightingale security and migration

This component defaults to ClusterIP, authenticated MySQL/Redis, no bundled
node collector, no agent API, and a non-root application with a read-only root
filesystem. NetworkPolicy allows only the release's internal traffic, DNS and
the default VictoriaMetrics writer. Allow trusted gateways, agents and notification
destinations explicitly in `networkPolicy.ingress` / `networkPolicy.egress`.
Adjust the VictoriaMetrics namespace/port if you change its endpoint. NodeLocal
DNS needs an additional DNS egress rule. Verify that your CNI enforces policies.

The local dependency contains official sources plus the patches in UPSTREAM.md.
Run `helm dependency build --skip-refresh` before rendering/installing the chart.
Use the rendered `install` script; it does not update remote chart repositories.

## First installation

Install into a dedicated namespace. Helm creates `<release>-bootstrap` with
independent random alphanumeric values: 24 characters for `admin-password`,
48 for `mysql-password`, `mysql-root-password`, and `redis-password`. The shorter
admin seed is intentional: Nightingale's InitRoot treats passwords >=32 characters
as already hashed; 24 random alphanumeric characters still provide about 143 bits
of entropy. InitRoot hashes it with the database salt on first start. The application
uses the `n9e` MySQL role, restricted to `n9e_v6.*`; root is only for DB administration.
The application config and seed SQL are Secrets, not ConfigMaps. Helm release
records also contain these values: restrict Secret and Helm release access.

Use `kubectl port-forward` on the n9e Service to sign in as `root`, retrieving
`admin-password` from the bootstrap Secret through your approved secret tooling.
Do not paste credentials into args, Git, PRs, shell arguments, or logs. Validate
login, create a rule, deliver an approved HTTP/SMTP notification, and verify the
VictoriaMetrics writer before allowing trusted network peers.

The bootstrap Secret is retained on uninstall and reused through Helm `lookup`
on upgrade. Back it up with the database. An upgrade without it fails closed.
Offline `helm template` generates preview credentials; **do not apply that output**
to an existing installation. Use Helm against the intended cluster so it can
reuse the existing Secret. Never use `--take-ownership` to adopt an unknown Secret.

## Existing installations: maintenance window required

The old chart used MySQL 5.7, a root application account and known passwords.
This revision also changes Nightingale to 9.1.1 and MySQL to 8.4 LTS. Do not mount
a 5.7 data directory into 8.4. Do not assume re-running initialization SQL changes
an existing administrator password.

1. Restrict the old public entry point immediately. Preserve incident evidence
   when compromise is suspected. Inventory notification scripts and credentials.
2. Back up and restore-test the old database, retained PVCs, application config,
   and Helm values. Stop writes and stop the old application before final export.
3. Rehearse a logical migration into a **new** MySQL 8.4 data volume, including
   schema compatibility and Nightingale schema migration. A physical/in-place
   upgrade instead requires the supported 5.7 -> 8.0 -> 8.4 path. The new mount
   uses the `mysql` subdirectory; changing the mount does not migrate old data.
4. Rotate the actual SQL application/root passwords and the actual Nightingale
   administrator password. The application role needs privileges on `n9e_v6.*`
   only, no global grants and no GRANT OPTION. Configure Redis authentication.
5. Create `<release>-bootstrap` with those **actual migrated values**, all random
   alphanumeric strings (admin: 24-31 characters; database/Redis: at least 32). Use Secret metadata owned by
   this Helm release (`app.kubernetes.io/managed-by: Helm`, annotations
   `meta.helm.sh/release-name` and `meta.helm.sh/release-namespace`) so Helm can
   manage it. Do not set this up while the old deployment is still publicly usable.
6. Render into a fresh output directory and review the resource diff, PVC names,
   policies and removal of the old Ingress/collector. After rehearsing, run install
   with `BLCLI_SECURITY_MIGRATION_APPROVED=1`. This gate also applies to direct
   subsequent installer upgrades; direct Helm users must follow the same procedure.
7. Check old credentials fail, new login works, rules evaluate, and notifications
   reach only approved destinations. Confirm no unexpected external LB or node
   mounts remain. Keep the old backups/volumes until the restore plan is accepted.

Changing the bootstrap Secret alone does not rotate passwords stored in databases.
Coordinate rotation with the application and Redis and restart affected Pods.

## Remaining privileged application features

Nightingale's administrator-controlled script notification feature remains in
the official image. The writable inline-script working directory and shipped
script mounts are removed, but this is **not** an application-level disable
switch: path-based execution and future execution features still require treating
an administrator as having code execution within the restricted Pod. Use HTTP/SMTP
notifications, keep administrator membership small, and review script channels.
The Pod has no Kubernetes token, node mounts or host network; egress is restricted.
