# Vendored official chart

Source: [n9e official upstream](https://github.com/flashcatcloud/n9e-helm/tree/00fe5e221abde7e28dc5741050e2b82685b82ab1)

Original archive SHA256: `f325ff1f25e4cb414cc80a5e25fd05299c190fc1560fcfc51076cc4ee7cb78b0`

Local dependency version ends in `-blcli.1`. Readable sources are in `vendor/`;
retain their upstream license/copyright. Changes: Nightingale image 9.1.1, MySQL 8.4.13, Redis 7.4.12; no bundled collector/Prometheus or script mount; ClusterIP; cached random bootstrap Secret; Secret config/SQL; schema-scoped MySQL account, Redis auth; non-root read-only application.

The wrapper also adds NetworkPolicy and an installer migration gate. To update,
fetch a reviewed upstream version, reapply these patches, run the security
regressions and container canaries, update the provenance and Chart.lock, then
review the complete rendered resource diff. Do not run dependency update against
an unreviewed upstream or silently replace the local source directory.
