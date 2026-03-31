# Istio

## Prerequisites

- **istioctl** must be in PATH. The install script checks for it before running.
- Optional: set `minIstioctlVersion` in component args to enforce a minimum version (e.g. `1.20.0`).

## Install

Run from this directory after rendering:

```bash
bash install
```

Uses the IstioOperator YAML (default `operator.yaml`) to install Istio via `istioctl install`.
