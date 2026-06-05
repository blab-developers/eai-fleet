import { defineConfig } from 'vite';
import { sveltekit } from '@sveltejs/kit/vite';

export default defineConfig({
  plugins: [sveltekit()],
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
  build: {
    // minify:false is load-bearing, not laziness. SvelteKit derives cssMinify from
    // build.minify (kit vite plugin: `cssMinify: minify == null ? true : !!minify`),
    // and any truthy minify forces vite 8's lightningcss CSS minifier — which throws
    // on Carbon's legacy `@media not all and (min-resolution >= 0.001dpcm)` hack.
    // Setting minify:false makes cssMinify false too, sidestepping lightningcss. The
    // bundle is tiny (a handful of Carbon components on one page) so it's a non-issue.
    minify: false,
  },
});
