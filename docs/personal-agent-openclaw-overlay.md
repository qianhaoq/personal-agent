# Personal Agent Fork Overlay

This repository is a public fork of `NousResearch/hermes-agent`. The fork keeps
Hermes Agent as the baseline runtime and adds a personal, local-first assistant
direction inspired by selected OpenClaw design strengths.

## Baseline: Keep Hermes as the Core

The fork should preserve these Hermes surfaces as the primary execution model:

- `run_agent.py` for the `AIAgent` conversation loop and provider dispatch.
- `model_tools.py`, `toolsets.py`, and `tools/registry.py` for tool discovery,
  schema exposure, and function-call execution.
- `hermes_state.py` for SQLite-backed session storage and FTS recall.
- `skills/` and `optional-skills/` for procedural memory and task recipes.
- `gateway/` for messaging platform entry points.
- `hermes_cli/` for setup, config, provider, tool, and diagnostic commands.

The fork should avoid copying the earlier lightweight `personal-agent` skeleton
back into this tree. That prototype proved the product direction, but Hermes now
owns the real runtime baseline.

## OpenClaw Ideas to Adopt

OpenClaw is strongest where Hermes is intentionally thinner: device control
plane design. The fork should borrow the ideas below while keeping Hermes'
Python runtime and package layout.

| OpenClaw idea | Adopted direction in this fork |
| --- | --- |
| Local-first gateway | Keep one long-lived Hermes gateway process as the control plane for local and remote clients. |
| Operator/node roles | Add a WebSocket control protocol where operators and companion nodes declare distinct roles during `connect`. |
| Device pairing | Require explicit pairing for non-local devices and persist approved device identity plus token state. |
| Declared node commands | Nodes must declare command capability snapshots; the gateway allowlist/denylist decides what can be invoked. |
| Event streams | Normalize lifecycle, assistant, tool, node, and health events for CLI, web, and mobile clients. |
| Remote access guidance | Prefer Tailscale or SSH tunnels; do not expose unauthenticated gateway ports. |

## First Implementation Track

Phase 1 should focus on Agent Core + Tools compatibility, then introduce the
OpenClaw-style control plane around it:

1. Keep Hermes tests green before adding fork-specific code.
2. Add a gateway WebSocket route for `role=operator` and `role=node`.
3. Add a device pairing store and CLI/web endpoints for pending/approved nodes.
4. Add `node.invoke` routing with an explicit command policy.
5. Expose node-originated context to `AIAgent` as normal tool/context input,
   rather than adding a separate agent runtime.

Phase 1 should not rename the Python package, replace the Hermes CLI, or ship
mobile apps. Native iOS/Android work should start after the wire protocol and
pairing model have tests.

## Safety Defaults

- Mobile and desktop nodes are peripherals, not gateway hosts.
- `system.run` on a node is off by default and must require a separate approval
  policy if implemented later.
- Loopback operator access can use local tokens, but LAN/tailnet access must use
  pairing and device-bound credentials.
- Gateway requests that cause side effects should include idempotency keys before
  being exposed to unreliable mobile networks.
- Fork-specific docs should distinguish confirmed Hermes behavior from planned
  OpenClaw-inspired extensions.

## Upstream Sync Policy

This fork should stay close to upstream Hermes:

- Keep `upstream=https://github.com/NousResearch/hermes-agent.git` as fetch-only.
- Prefer additive fork-specific modules and docs over broad edits to upstream
  files.
- Keep dependency pins and Python version policy aligned with upstream unless a
  fork-specific change has a clear security or packaging reason.
- Use focused conventional commits with decision-context trailers for fork-only
  changes.
