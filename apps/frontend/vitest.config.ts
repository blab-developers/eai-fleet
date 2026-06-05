import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vitest/config';

export default defineConfig({
  // The SvelteKit plugin resolves $lib + the $env/* virtual modules and compiles
  // .svelte files, so unit tests import exactly like the app does — no alias stubs.
  plugins: [sveltekit()],
  test: {
    globals: true,
    environment: 'happy-dom',
    setupFiles: ['./tests/setup.ts'],
    // Vitest owns unit tests (*.test.ts); Playwright owns e2e (*.spec.ts).
    include: ['tests/**/*.test.ts'],
    exclude: ['node_modules/**', 'tests/e2e/**'],
  },
});
