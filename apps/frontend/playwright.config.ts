import { defineConfig, devices } from '@playwright/test';

/**
 * E2E config. The frontend is driven in isolation: every test mocks `/api/*` in the
 * browser (page.route), so no backend / Prometheus / k8s is needed — the suite is
 * deterministic. EAI_FLEET_FRONTEND_GRAFANA_URL is set here so the per-device "History"
 * link renders with a known base.
 *
 * The webServer runs the PRODUCTION build (adapter-node `node build`), NOT `vite dev`:
 * the dev server pre-bundles deps on the first navigation, which stalls the first test
 * (the source of "cold start" flake). The built server has no per-request compile, so
 * the suite is stable WITHOUT retries and exercises the real artifact. `yarn test:e2e`
 * runs `vite build` first (see package.json) so `build/` exists.
 */
const PORT = 4173;
const GRAFANA = 'https://grafana.test/d/eai-fleet';

export default defineConfig({
  testDir: 'tests/e2e',
  // Serial: the suite shares one server (mocked /api), so parallel workers just contend.
  fullyParallel: false,
  workers: 1,
  forbidOnly: !!process.env.CI,
  // No local retries — the built server doesn't flake. CI keeps one retry as a guard
  // against transient infra hiccups only.
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [['list'], ['html', { open: 'never' }]] : 'list',
  use: {
    baseURL: `http://localhost:${PORT}`,
    trace: 'on-first-retry',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: {
    command: 'node build',
    url: `http://localhost:${PORT}`,
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
    env: {
      PORT: String(PORT),
      EAI_FLEET_FRONTEND_GRAFANA_URL: GRAFANA,
    },
  },
});
