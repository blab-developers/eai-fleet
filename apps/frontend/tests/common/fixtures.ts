import { test as base, expect, type Page, type Route } from '@playwright/test';
import type { DeviceView, FleetView } from '../../src/lib/generated/fleet-backend-api';

export const sampleDevices: DeviceView[] = [
  { device_id: 'jetson-00', name: 'jetson-00', state: 'running', fps: 29.5, gpu_utilization: 73, health: 'online', chromium_running: true },
  { device_id: 'jetson-01', name: 'jetson-01', state: 'stopped', fps: 0, gpu_utilization: 0, health: 'online', chromium_running: false },
  { device_id: 'jetson-02', name: 'jetson-02', state: 'stopped', fps: 0, gpu_utilization: 0, health: 'offline', chromium_running: null },
];

// Backend-injected demo devices (each marked demo=true) — used to exercise the
// frontend show/hide toggle. Mirrors what `GET /devices` returns when the real
// derived fleet is empty and EAI_FLEET_DEMO_MODE is on.
export const demoDevices: DeviceView[] = [
  { device_id: 'demo-00', name: 'demo-00', state: 'running', fps: 30, gpu_utilization: 60, health: 'online', chromium_running: true, demo: true },
  { device_id: 'demo-01', name: 'demo-01', state: 'stopped', fps: 0, gpu_utilization: 0, health: 'online', chromium_running: false, demo: true },
  { device_id: 'demo-02', name: 'demo-02', state: 'stopped', fps: 0, gpu_utilization: 0, health: 'offline', chromium_running: null, demo: true },
];

export function fleetView(devices: DeviceView[]): FleetView {
  return {
    devices,
    total: devices.length,
    online: devices.filter((d) => d.health === 'online').length,
  };
}

export function json(status: number, body: unknown) {
  return { status, contentType: 'application/json', body: JSON.stringify(body) };
}

export async function mockFleet(page: Page, body: unknown, status = 200): Promise<void> {
  await page.route(
    (url) => url.pathname === '/api/fleet/devices',
    (route: Route) =>
      route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) }),
  );
}

export async function mockSetImage(
  page: Page,
  handler: (route: Route, deviceId: string) => unknown,
): Promise<void> {
  await page.route(
    (url) => /^\/api\/fleet\/devices\/[^/]+\/inference\/image$/.test(url.pathname),
    (route) => {
      const id = new URL(route.request().url()).pathname.split('/')[4];
      return handler(route, id);
    },
  );
}

// Extend base test with a mockedPage fixture.
// This page has the default devices API mocked and ready.
export const test = base.extend<{
  mockedPage: Page;
}>({
  mockedPage: async ({ page }, use) => {
    await mockFleet(page, fleetView(sampleDevices));
    await use(page);
  },
});

export { expect };
