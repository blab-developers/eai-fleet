import { defineConfig, type Plugin } from 'vite';
import { sveltekit } from '@sveltejs/kit/vite';
import { optimizeCss } from 'carbon-preprocess-svelte';

/**
 * Fix Carbon v11's INVALID media query at the source. carbon-components-svelte ships
 * `@media not all and (min-resolution >= 0.001dpcm)` (a Safari hack), which is illegal
 * CSS — the `min-` prefix can't be combined with the `>=` range operator — so vite 8's
 * default lightningcss minifier (correctly) rejects it. Rewrite it to the valid
 * `(resolution >= 0.001dpcm)` form Carbon already uses elsewhere, BEFORE minify, so the
 * output is valid + fully minified with no warnings. Upstream: carbon-design-system/
 * carbon#19070 (no fixed carbon-components-svelte@1.0.0-next release yet); this no-ops
 * once that lands. Beats lightningcss `errorRecovery`, which only silenced the error.
 */
function fixCarbonInvalidMediaQuery(): Plugin {
  return {
    name: 'fix-carbon-invalid-media-query',
    enforce: 'pre',
    transform(code) {
      if (!code.includes('min-resolution >=')) return null;
      return { code: code.replaceAll('min-resolution >=', 'resolution >='), map: null };
    },
  };
}

export default defineConfig({
  // optimizeCss purges the unused Carbon stylesheet from the production bundle (we use a
  // handful of components on one page). Build-only — skipped under `vitest` so unit tests
  // don't pay for it.
  plugins: [
    fixCarbonInvalidMediaQuery(),
    sveltekit(),
    ...(process.env.VITEST ? [] : [optimizeCss()]),
  ],
  // No vite `server.proxy` for /api: SvelteKit runs hooks.server.ts under `vite dev` too,
  // so the same proxy handles dev and prod. Set EAI_FLEET_BACKEND_URL in .env (see
  // .env.example) to point dev at a running backend.
  server: {
    port: 5173,
    host: true,
  },
  preview: {
    port: 5173,
    host: true,
  },
});
