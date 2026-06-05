import adapter from '@sveltejs/adapter-node';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

export default {
  preprocess: [vitePreprocess()],
  kit: {
    // adapter-node: the frontend ships as a self-contained Node server (`node build`)
    // in its own Docker container. hooks.server.ts proxies /api/* to the backend
    // container — so no nginx/ingress is needed for the eai-infra docker deploy.
    adapter: adapter(),
    alias: {
      $lib: 'src/lib',
    },
    // Public env (browser-readable) is prefixed EAI_FLEET_FRONTEND_ — read at runtime
    // via $env/dynamic/public so the eai-infra role can set EAI_FLEET_FRONTEND_GRAFANA_URL
    // on the container without a rebuild. The backend-proxy target
    // (EAI_FLEET_BACKEND_URL) is PRIVATE (server-only) and read in hooks.server.ts.
    env: {
      publicPrefix: 'EAI_FLEET_FRONTEND_',
    },
  },
};
