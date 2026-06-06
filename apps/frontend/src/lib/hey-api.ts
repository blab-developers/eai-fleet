/**
 * Runtime configuration for the generated @hey-api client (called once at client
 * creation via `runtimeConfigPath`).
 *
 * baseUrl resolution, in order:
 *   1. `EAI_FLEET_FRONTEND_API_BASE_URL` if set — an explicit override (e.g. point dev at
 *      a remote backend). Runtime env (`$env/dynamic/public`) so adapter-node reads it at
 *      request time, no rebuild.
 *   2. otherwise the generated client's default — which, since the backend OpenAPI
 *      declares no `servers`, is **relative/same-origin**: requests go to `/api/*` on this
 *      origin and `hooks.server.ts` proxies them to the backend (EAI_FLEET_BACKEND_URL).
 *
 * No hardcoded URL and no `''` sentinel — same-origin is the library default, the override
 * is env-driven.
 */

import { env } from '$env/dynamic/public';
import type { CreateClientConfig } from '$lib/generated/fleet-backend-api/client.gen';

export const createClientConfig: CreateClientConfig = (config) => ({
  ...config,
  baseUrl: env.EAI_FLEET_FRONTEND_API_BASE_URL ?? config?.baseUrl,
});
