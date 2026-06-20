# Fleet frontend testing — the 2026 Svelte stack

Three tiers, the same strategy as **eai-nano (ADR-013)**. The frontends do not share UX code; they
share the test *approach* so a reviewer moving between repos sees one pattern.

| Tier | Files | Runs in | Command |
|------|-------|---------|---------|
| **Logic** | `tests/**/*.test.ts` | node | `yarn test:logic` |
| **Components** | `tests/**/*.svelte.test.ts` | **real Chromium** (Playwright provider) | `yarn test:components` |
| **Flows** | `tests/e2e/**/*.spec.ts` | real browser, full stack | `yarn test:e2e` |

`yarn test:unit` runs logic then components (the two vitest projects run as separate invocations —
a single combined `vitest run` hits an SSR/client transform-cache conflict).

## Why these tiers (and not happy-dom / @testing-library)

- **No simulated DOM.** `happy-dom`/`jsdom` mis-handle Svelte 5 runes (`$state`/`$derived`) and never
  actually render our Carbon components. They were removed — the logic suites never needed a DOM, and
  component behaviour belongs in a *real* browser.
- **Components — `vitest-browser-svelte`.** Renders the real component in real Chromium and queries
  with **locators** (`page.getByRole`/`getByText`), never container queries. See
  `EmptyState.svelte.test.ts` (`$derived` copy across prop combos), `PageHeader.svelte.test.ts`
  (render + optional description), `ErrorRetry.svelte.test.ts` (button interaction + a mocked `$lib`
  store seam).

## Carbon quirk (load-bearing config)

`carbon-components-svelte` ships **legacy (Svelte-4-syntax)** components. esbuild-prebundling them
breaks Svelte 5 prop fallbacks under the client runtime (a `get_fallback` null deref) the moment one
actually renders — so `vitest.config.ts` sets `optimizeDeps: { exclude: ['carbon-components-svelte'] }`,
which makes the Svelte plugin compile them in legacy-compat mode instead. Removing that line makes
every Carbon component test crash. (Same line, same reason, in eai-nano's config.)
