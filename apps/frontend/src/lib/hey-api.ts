/**
 * Runtime configuration for the generated @hey-api client.
 *
 * `createClientConfig` is invoked once when the generated client is created
 * (src/lib/generated/fleet-backend-api/client.gen.ts), so this applies to every SDK
 * call without any hand-written wrapper.
 *
 * baseUrl is always '' (relative): every request goes out same-origin as `/api/*` and
 * hooks.server.ts proxies it to the backend container — in both `yarn dev` and the
 * deployed adapter-node server. An absolute URL would bypass that proxy.
 */

import type { CreateClientConfig } from '$lib/generated/fleet-backend-api/client.gen';

export const createClientConfig: CreateClientConfig = (config) => ({
  ...config,
  baseUrl: '',
});
