# Safety API

The `client.safety` namespace exposes the safety control plane, rule registry, and checkpoint mechanism. Use it to inspect, tune, and trigger human-in-the-loop review.

## SDK proxy

::: crp.sdk.proxies._SafetyProxy
    options:
      show_source: false
      filters: ["!^_"]

## Safety Control Plane

::: crp.security.control_plane.SafetyControlPlane
    options:
      show_source: false
      filters: ["!^_"]

## Checkpoint

::: crp.security.checkpoint.Checkpoint
    options:
      show_source: false
      filters: ["!^_"]
