import { defineConfig, devices } from '@playwright/test';

/**
 * E2E config. The frontend is driven in isolation: every test mocks `/api/*` in the
 * browser (page.route), so no backend / Prometheus / k8s is needed — the suite is
 * deterministic and runs on a node-only CI image. EAI_FLEET_FRONTEND_GRAFANA_URL is
 * set here so the per-device "History" link renders with a known base.
 */
const PORT = 4173;
const GRAFANA = 'https://grafana.test/d/eai-fleet';

export default defineConfig({
  testDir: 'tests/e2e',
  // Serial: the suite shares one vite dev server (mocked /api), so parallel workers
  // just contend on it. The suite is small — serial is stable and fast enough.
  fullyParallel: false,
  workers: 1,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [['list'], ['html', { open: 'never' }]] : 'list',
  use: {
    baseURL: `http://localhost:${PORT}`,
    trace: 'on-first-retry',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: {
    command: `vite dev --port ${PORT} --strictPort`,
    url: `http://localhost:${PORT}`,
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
    env: {
      EAI_FLEET_FRONTEND_GRAFANA_URL: GRAFANA,
    },
  },
});
