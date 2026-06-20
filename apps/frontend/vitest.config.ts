import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vitest/config';
import { playwright } from '@vitest/browser-playwright';

// 2026 Svelte-5 testing stack — the SAME three tiers as eai-nano (ADR-013); UX code is not shared
// across the two frontends, the test STRATEGY is. A two-project split:
//   - `unit`    — pure TS logic in Node (`*.test.ts`): stores, error mapping, demo/model helpers.
//   - `browser` — component behaviour in a REAL browser (`*.svelte.test.ts`) via the Playwright
//                 provider (Chromium). Replaces happy-dom, which mis-handles Svelte 5 runes
//                 (`$state`/`$derived`) and never actually rendered our Carbon components.
// Playwright still owns full-stack flows (tests/e2e/*.spec.ts).
// A single `vitest run` over BOTH projects hits an SSR/client transform-cache conflict, so the
// projects run as SEPARATE invocations — `test:unit` = unit then browser (see package.json).
export default defineConfig({
	plugins: [sveltekit()],
	// Carbon ships LEGACY (Svelte-4-syntax) components; esbuild-prebundling them breaks Svelte-5
	// prop fallbacks under the client runtime (get_fallback null deref). Exclude so the Svelte
	// plugin compiles them in proper legacy-compat mode — the browser tier can then render Carbon.
	optimizeDeps: { exclude: ['carbon-components-svelte'] },
	test: {
		// vitest browser scratch lives under .cache (CACHE_DIR convention), never the source tree.
		attachmentsDir: '.cache/vitest-browser/attachments',
		projects: [
			{
				extends: true,
				test: {
					name: 'unit',
					environment: 'node',
					globals: true,
					setupFiles: ['./tests/setup.ts'],
					include: ['tests/**/*.test.ts'],
					exclude: ['tests/**/*.svelte.test.ts', 'node_modules/**', 'tests/e2e/**']
				}
			},
			{
				extends: true,
				test: {
					name: 'browser',
					globals: true,
					include: ['tests/**/*.svelte.test.ts'],
					browser: {
						enabled: true,
						provider: playwright(),
						headless: true,
						screenshotDirectory: '.cache/vitest-browser/screenshots',
						// headless ALSO per-instance: vitest-5 beta reads it here, not the top-level field.
						instances: [{ browser: 'chromium', headless: true }]
					}
				}
			}
		]
	}
});
