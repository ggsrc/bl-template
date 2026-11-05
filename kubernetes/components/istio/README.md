# Istio

## Prerequisites

- **istioctl** must be in PATH. `istioctl install` renders the charts bundled with istioctl itself, so use the istioctl release that matches `IstioVersion` (default `1.31.3`). The install script refuses an istioctl older than that version (or than `minIstioctlVersion`, if set) and warns about a different minor version.

## Install

Run from this directory after rendering:

```bash
bash install
```

Uses the IstioOperator YAML (default `operator.yaml`) to install Istio via `istioctl install`.

## Upgrades

In-place upgrades may skip at most one minor version, so the install script stops when the running istiod is more than one minor version behind `spec.tag` (override with `ISTIO_ALLOW_MINOR_SKIP=1`). Step through each minor version (set `spec.tag` in `operator.yaml` and use the matching istioctl), or use a revision-based canary upgrade, then restart workloads that have sidecars (`kubectl rollout restart deployment -n <namespace>`).

## Security-related parameters

- `EnableAutoMtls` (default `true`): sidecars use mTLS towards workloads that have a sidecar. Servers stay PERMISSIVE unless you add a `PeerAuthentication`; switch a namespace to `STRICT` only once every client in it has a sidecar.
- `IngressGatewayLoadBalancerSourceRanges` (default empty = open to `0.0.0.0/0`): client CIDRs allowed to reach the ingress gateway load balancer.
- `IngressGatewayExternalTrafficPolicy` (default empty = `Cluster`): `Local` keeps the client source IP, which IP-based `AuthorizationPolicy` rules need. With `Local`, only nodes running a gateway pod receive traffic, so set `IngressGatewayReplicaCount` to 2 or more and add a PodDisruptionBudget before you switch; the switch also reprograms the load balancer health check.
