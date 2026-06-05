import { test, expect } from '@playwright/test';
import { fleetView, mockFleet, sampleDevices } from './mocks';

test.describe('fleet view', () => {
  test('summary tiles reflect the fleet counts', async ({ page }) => {
    await mockFleet(page, fleetView(sampleDevices));
    await page.goto('/');

    await expect(page.getByTestId('summary-total')).toHaveText('3');
    await expect(page.getByTestId('summary-online')).toHaveText('2');
    await expect(page.getByTestId('summary-offline')).toHaveText('1');
  });

  test('renders one accordion row per device with health tag + fps', async ({ page }) => {
    await mockFleet(page, fleetView(sampleDevices));
    await page.goto('/');

    await expect(page.getByTestId(/^device-title-/)).toHaveCount(3);

    const online = page.getByTestId('device-title-jetson-00');
    await expect(online).toContainText('jetson-00');
    await expect(online).toContainText('29.5 fps');
    await expect(online.locator('.bx--tag--green')).toBeVisible();

    const offline = page.getByTestId('device-title-jetson-02');
    await expect(offline.locator('.bx--tag--red')).toBeVisible();
  });

  test('expanding a device reveals its metrics', async ({ page }) => {
    await mockFleet(page, fleetView(sampleDevices));
    await page.goto('/');

    await page.getByTestId('device-title-jetson-00').click();

    const body = page.getByTestId('device-body-jetson-00');
    await expect(body.getByTestId('metric-state')).toHaveText('running');
    await expect(body.getByTestId('metric-fps')).toHaveText('29.5');
    await expect(body.getByTestId('metric-gpu')).toHaveText('73%');
    await expect(body.getByTestId('metric-health')).toHaveText('online');
  });

  test('Grafana history link deep-links to the device', async ({ page }) => {
    await mockFleet(page, fleetView(sampleDevices));
    await page.goto('/');

    await page.getByTestId('device-title-jetson-01').click();
    const link = page.getByTestId('device-body-jetson-01').getByRole('link', { name: /History/ });
    await expect(link).toHaveAttribute('href', 'https://grafana.test/d/eai-fleet?var-device=jetson-01');
    await expect(link).toHaveAttribute('target', '_blank');
  });

  test('empty fleet shows the empty state', async ({ page }) => {
    await mockFleet(page, fleetView([]));
    await page.goto('/');

    await expect(page.getByText('No devices in the fleet yet.')).toBeVisible();
    await expect(page.getByTestId('summary-total')).toHaveText('0');
  });

  test('a 502 (Prometheus down) surfaces an error banner, not a crash', async ({ page }) => {
    await mockFleet(page, { detail: 'Prometheus query failed: boom' }, 502);
    await page.goto('/');

    await expect(page.getByText('Fleet view unavailable')).toBeVisible();
    await expect(page.getByText('Prometheus query failed: boom')).toBeVisible();
  });
});
