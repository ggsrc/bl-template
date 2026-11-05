# Grafana

## Prerequisites

- **helm** and **kubectl** must be in PATH. The install script checks for them before running.
- Optional: set `minHelmVersion` / `minKubectlVersion` in component args to enforce minimum versions.

## Install

After rendering (run `blcli init` first to generate values-corp.yaml), run:

```bash
bash install
```

The install uses `values.yaml values-corp.yaml`; `values-corp.yaml.tmpl` is rendered by blcli, with parameters in args.yaml (imageTag, rootUrl, vmDatasourceUrl, lokiDatasourceUrl, hostedDomain, etc.).

Or manually:

```
helm dependency build
helm install grafana -n grafana . --values ./values.yaml --values ./values-corp.yaml
helm upgrade grafana -n grafana . --values ./values.yaml --values ./values-corp.yaml
```

If you do not render with blcli, create values-corp.yaml yourself by copying and editing values-corp.yaml.tmpl.

## Versions and supply chain

- Chart `grafana` 11.6.1 from `oci://ghcr.io/grafana-community/helm-charts` (helm 3.8 or newer), Grafana image 12.4.13.
- `install` runs `helm dependency build`, which only installs the version recorded in `Chart.lock`, and checks the chart archive's sha256. To bump the chart, run `helm dependency update`, commit `Chart.lock`, and update `CHART_ARCHIVE`/`CHART_SHA256` in `install.tmpl`.
- Plugins are pinned as `<id>@<version>`; unpinned plugins would be fetched at their latest version on every pod start.

## Sign-in

- Google login only admits accounts whose e-mail is in `hostedDomain` (rendered as `auth.google` `allowed_domains`; `hosted_domain` alone is just a hint to Google's account chooser). Set it to your Google Workspace or Cloud Identity domain; the default `example.com` admits nobody.
- Optional `allowedGroups` (space-separated Google group e-mails) further limits sign-in to members of those groups.
- With a consumer Gmail account there is no domain to restrict: keep the OAuth consent screen in "Testing" with an explicit list of test users, or keep Grafana private.
- Session cookies are marked `Secure`, so serve Grafana over HTTPS (`root_url`).
