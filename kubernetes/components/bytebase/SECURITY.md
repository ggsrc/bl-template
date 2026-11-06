# Bytebase security and migration

New installs use Bytebase 3.24.0, a non-root UID/GID 113, a read-only root filesystem,
no Kubernetes service-account token, dropped capabilities and RuntimeDefault seccomp.
NetworkPolicy blocks all incoming traffic until an administrator explicitly allows
trusted peers. Keep it enabled and confirm your CNI enforces it; restrict namespace
administration and port-forward RBAC. NodeLocal DNS may need an extra DNS egress rule.

The default `metadataDatabase.enabled: true` creates a CNPG PostgreSQL cluster
`<release>-postgresql` with superuser login disabled. Bytebase gets `PG_URL` from
the generated `<release>-postgresql-app` Secret's `uri` key. Install CNPG first.
The Bytebase data volume remains mounted for application data, not its metadata DB.

To use an existing external metadata DB, set `metadataDatabaseEnabled: false` and
`existingPgURLSecret` / `existingPgURLSecretKey` in args (or equivalent chart values).
Use a dedicated application role owning the Bytebase database, not a superuser.
Add narrowly scoped DB egress to `networkPolicy.egress`. Embedded metadata DB is
not allowed. Inline connection passwords and the legacy escape-password mechanism
are not supported by this hardened profile.

## First installation and registration

1. Install in a dedicated namespace with the default **empty ingress allowlist**.
2. Use an authorized `kubectl port-forward` to port 8080 to register the first
   administrator. The first successful registration becomes the administrator.
3. Disable self-service signup in workspace settings, and confirm anonymous signup
   fails server-side. **This feature requires a suitable Bytebase license.** If your
   edition cannot enforce it, keep access behind an authenticated identity gateway
   restricted to the approved user group; do not claim signup is disabled.
4. Configure identity, application roles and audit settings. Allow only your
   authenticated gateway's namespace + Pod selector to port 8080 in
   `networkPolicy.ingress`. Do not expose the ClusterIP through a public route
   without that authentication boundary. Verify direct/unapproved access fails.
5. Add approved target-database egress rules. Validate a real database review/change
   using a disposable test DB with a least-privilege role before production access.

Bytebase 3.24.0 removed `--disable-sample` / `--disable-metric`; they are not passed
by this chart. Its self-host sample creation requires embedded metadata PostgreSQL,
which this profile disallows. **Existing sample instances/data must still be
removed during migration**; using an external DB is not proof that old samples
were removed. Do not use the onboarding wizard's sample-instance option.

## Existing installations: do not upgrade the image against old data blindly

The installer requires `BLCLI_SECURITY_MIGRATION_APPROVED=1` only when the deployed
wrapper chart is older than 2.0.0 (including Bytebase 1.1.1 from the first hardening
PR). New installs and subsequent 2.x upgrades do not require it. Python 3 is needed
to parse the Helm release list; unreadable/unknown metadata fails closed.
This is an operator acknowledgment, not an automatic migration or security check.

1. Close the public entry point, preserve incident evidence if relevant, and audit
   users, sessions, SQL activity, sample DBs and all target credentials. Rotate
   credentials and accessible identities if compromise is established.
2. Back up and restore-test metadata PostgreSQL, PVC data and configuration.
   Follow Bytebase's release-by-release upgrade requirements from the current
   version; rehearse the full path in isolation. In-place downgrade is unsupported.
3. Stop **all** Bytebase replicas before the final 3.24.0 migration. Export/restore
   embedded metadata into a dedicated external PostgreSQL DB; do not point a new
   empty CNPG database at a populated installation and mistake it for a migration.
   Keep a restore point for the entire metadata database and old application image.
4. Remove sample instances through Bytebase, stop their processes and retire the
   sample data only after verifying it is disposable. Fix data-volume ownership for
   UID/GID 113 in the maintenance window; this chart does not run a privileged
   recursive chown init container against existing volumes.
5. Review the generated resource diff and PVCs. If using an existing metadata DB,
   disable creation of the new CNPG cluster and provide its URI Secret. Add required
   DB/gateway/DNS egress. Run the installer only after the rehearsal succeeds.
6. Verify old accounts/sessions cannot authenticate, anonymous signup is denied or
   the identity gateway blocks it, no samples run, the Pod runs non-root, and a
   disposable database review/change passes. Keep the old backups until accepted.

3.24.0 also changes SQL Server/Oracle TLS handling: review and re-enable the
appropriate certificate verification after supplying a trusted CA. Follow the
[official upgrade notes](https://github.com/bytebase/bytebase/releases/tag/3.24.0).

## Failed first installation and retry

A failed release using a 2.x wrapper can be retried without migration approval.
Keep its original metadata database and URI Secret; do not replace them with
an empty database. The 1.1.1 wrapper remains gated once, even if it already ran
Bytebase 3.24.0. Review the existing data and connection before acknowledging.
