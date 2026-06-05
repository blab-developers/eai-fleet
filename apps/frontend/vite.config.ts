import { defineConfig } from 'vite';
import { sveltekit } from '@sveltejs/kit/vite';
import { optimizeCss } from 'carbon-preprocess-svelte';

export default defineConfig({
  // vite 8 made lightningcss the default CSS minifier (vitejs/vite#21911), and it
  // throws "Invalid media query" on Carbon v11's legacy `@media not all and
  // (min-resolution >= 0.001dpcm)` hack. We can't switch to esbuild: SvelteKit forces
  // `cssMinify = !!build.minify` and its config wins, so `build.cssMinify: 'esbuild'`
  // is ignored. errorRecovery downgrades that parse error to a warning — so CSS still
  // minifies (lightningcss) AND JS still minifies (oxc); full production minification.
  css: { lightningcss: { errorRecovery: true } },
  // optimizeCss purges the unused Carbon stylesheet from the production bundle (we use
  // a handful of components on one page). Build-only — skipped under `vitest` so unit
  // tests don't pay for it.
  plugins: [sveltekit(), ...(process.env.VITEST ? [] : [optimizeCss()])],
  // No vite `server.proxy` for /api: SvelteKit runs hooks.server.ts under `vite dev`
  // too, so the same proxy handles dev and prod. Set EAI_FLEET_BACKEND_URL in .env
  // (see .env.example) to point dev at a running backend.
  server: {
    port: 5173,
    host: true,
  },
  preview: {
    port: 5173,
    host: true,
  },
});
