# AI-assisted interactive frontend workflow in eai-fleet

This document explains how AI coding agents (e.g. Kimi Code CLI) can work with
the `eai-fleet` frontend **interactively** — by driving a real browser against a
running dev server, making code changes, and verifying the result visually.

## What MCP is

MCP (Model Context Protocol) servers are small helper programs that extend an AI
coding agent's capabilities. They run as child processes of the AI client and
communicate over stdin/stdout. Each AI client maintains its own MCP
configuration; servers configured for Claude Desktop are not automatically
visible to Kimi Code CLI, and vice versa.

For frontend work, the useful MCP server is **Chrome DevTools**, which lets the
agent control a Chromium browser: navigate pages, take snapshots/screenshots,
click elements, type into inputs, evaluate JavaScript, and inspect network
requests and console messages.

## Current project setup

- **Kimi Code CLI** (`~/.kimi/mcp.json`) has the `chrome-devtools` MCP server
  configured for browser automation.
- The fleet frontend is a SvelteKit app in `apps/frontend/`.
- It proxies `/api/*` to the backend via `src/hooks.server.ts` (adapter-node).

To register the Chrome DevTools MCP server for Kimi Code CLI, place this in
`~/.kimi/mcp.json` and restart Kimi Code CLI:

```json
{
  "mcpServers": {
    "chrome-devtools": {
      "command": "npx",
      "args": ["-y", "chrome-devtools-mcp@latest"]
    }
  }
}
```

## How interactive frontend work happens

A typical interactive session looks like this:

1. **Agent reads the codebase** — routes, components, stores, tests, and this
   document.
2. **Agent starts the frontend dev server**:
   ```bash
   cd apps/frontend
   yarn install   # if needed
   yarn dev       # serves on http://localhost:5176 by default
   ```
3. **Agent supplies backend data** so the UI has something to render. Options:
   - Run the real fleet backend (requires Prometheus + k8s access).
   - Point `EAI_FLEET_BACKEND_URL` in `apps/frontend/.env` at a running backend.
   - Use the included mock server (`yarn mock:backend` or
  `python scripts/mock-backend.py`) which serves a static `FleetView` on
  `/api/fleet/devices` and accepts `POST /api/fleet/devices/{id}/inference/image`.
4. **Agent opens the browser** via the Chrome DevTools MCP and navigates to the
   local dev URL.
5. **Agent explores the page**:
   - Take an accessibility snapshot to read headings, buttons, inputs, links.
   - Take a screenshot to verify visual styling.
   - Click accordions, type into the "Set inference image" input, click Apply.
6. **Agent inspects state** by evaluating JavaScript in the page, e.g.
   `window.__sveltekit?.route`, the `fleetStore` object, or API response bodies.
7. **Agent makes a code change** and reloads the page.
8. **Agent re-checks** the snapshot/screenshot/console to confirm the change.
9. **Agent runs the automated checks**:
   ```bash
   yarn check           # svelte-check + TypeScript
   yarn test:logic      # Vitest — pure-logic tests in node (*.test.ts)
   yarn test:components # Vitest — component tests in REAL Chromium (*.svelte.test.ts)
   yarn test:unit       # both of the above (logic then components)
   yarn test:e2e        # Playwright (builds + runs E2E)
   ```
   The three test tiers are the 2026 Svelte stack — see [`apps/frontend/tests/README.md`](../apps/frontend/tests/README.md)
   and eai-nano ADR-013.

## Minimal mock backend for UI-only work

When you only want to change layout, copy, or styling, you do not need the real
Prometheus cluster. A minimal mock server in any language that responds to two
routes is enough:

- `GET /api/fleet/devices` → returns a `FleetView` JSON object.
- `POST /api/fleet/devices/{device_id}/inference/image` → returns a success
  payload like `{"scope": "fleet", "note": "DaemonSet patched"}`.

Example static `FleetView`:

```json
{
  "total": 2,
  "online": 1,
  "offline": 1,
  "devices": [
    {
      "device_id": "nano-01",
      "name": "OR-1 Nano",
      "state": "running",
      "health": "online",
      "fps": 14.3,
      "gpu_utilization": 67.5
    },
    {
      "device_id": "nano-02",
      "name": "OR-2 Nano",
      "state": "stopped",
      "health": "offline",
      "fps": 0.0,
      "gpu_utilization": 0.0
    }
  ]
}
```

Point the frontend at it via `apps/frontend/.env`:

```bash
EAI_FLEET_BACKEND_URL=http://localhost:8088
EAI_FLEET_FRONTEND_GRAFANA_URL=http://localhost:3000
```

## Capabilities the agent can use

With the Chrome DevTools MCP, the agent can:

- **Navigate** to `http://localhost:5176` or any route.
- **Take accessibility snapshots** to see the page structure and element `uid`s.
- **Take screenshots** (full page or single element) to verify rendering.
- **Click, hover, drag, and type** — exactly like a user.
- **Fill forms** all at once (e.g. enter an image tag and submit).
- **Evaluate JavaScript** in the page context to inspect Svelte stores, props,
  or DOM state.
- **Read console messages** and **network requests** to debug API calls.
- **Emulate viewports / dark mode / network conditions**.
- **Run Lighthouse** accessibility/SEO/best-practice audits.
- **Record performance traces** to diagnose slow renders.

## Step-by-step example: change the summary cards

Suppose you want the summary cards to show labels under the numbers instead of
above them.

1. Agent takes a snapshot/screenshot of `http://localhost:5176` to see the
   current summary.
2. Agent edits `apps/frontend/src/routes/+page.svelte`, changing the `.summary`
   / `.metric` CSS grid layout.
3. Agent reloads the page.
4. Agent takes another screenshot and confirms the labels are now below the
   numbers.
5. Agent runs `yarn check` and `yarn test:unit` to catch regressions.
6. If Playwright tests exist for the summary, agent runs `yarn test:e2e`.

## When to use interactive work vs. static editing

| Situation | Best approach |
|-----------|---------------|
| Pure logic change (store, error handling) | Edit logic into `$lib`, add a `*.test.ts`, run `yarn test:logic` |
| Carbon component behavior (rendered title/state, derived copy) | Add a `*.svelte.test.ts` (real Chromium), run `yarn test:components` |
| New user interaction (click flows, forms) | `*.svelte.test.ts` for the component-local interaction + Playwright for the full flow |
| Debugging an error that only appears in browser | Use MCP console/network inspection |
| Accessibility / responsive layout issues | Use MCP screenshots + Lighthouse |

## Safety notes

- The agent only operates on local `localhost` URLs; it cannot (and should not)
  touch production deployments.
- The Chrome DevTools MCP shares the user's normal Chrome profile; be mindful
  if sensitive sessions are open in other tabs.
- Always run `yarn check` and the relevant tests before committing, per
  `AGENTS.md`.
- Do not commit generated files from `.svelte-kit/`, `node_modules/`, or local
  `.env` files.

## Do we need a database or Prometheus MCP?

No. `eai-fleet` is stateless: fleet state is derived from Prometheus at read
time and exposed through the backend's REST API. All storage operations that
matter to the frontend go through `/api/fleet/*`, so a database or Prometheus
MCP server is not required for normal AI-assisted frontend work.
