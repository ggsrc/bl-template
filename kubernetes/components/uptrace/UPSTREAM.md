# Vendored official chart

Source: [uptrace official upstream](https://charts.uptrace.dev/uptrace-2.0.1.tgz)

Original archive SHA256: `151b728040fb8fc86bd448bf8e3464bc8b350d577f572de3a13c12626b057d9a`

Local dependency version ends in `-blcli.1`. Readable sources are in `vendor/`;
retain their upstream license/copyright. Changes: Two-level application values; no ingress or bundled collectors; cached random bootstrap Secret; Secret application config; generated ClickHouse hash and matching SecretKeyRef; restricted source CIDR; no app service-account token.

The wrapper also adds NetworkPolicy and an installer migration gate. To update,
fetch a reviewed upstream version, reapply these patches, run the security
regressions and container canaries, update the provenance and Chart.lock, then
review the complete rendered resource diff. Do not run dependency update against
an unreviewed upstream or silently replace the local source directory.
