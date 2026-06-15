import { test, expect } from '@playwright/test';
import { fleetView, mockFleet, sampleDevices } from './mocks';

test.describe('fleet view', () => {
  test('shows a loading skeleton while the first load is in flight', async ({ page }) => {
    // Delay the response so the skeleton is visible long enough to assert.
    await page.route(
      (url) => url.pathname === '/api/fleet/devices',
      async (route) => {
        await new Promise((resolve) => setTimeout(resolve, 200));
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(fleetView(sampleDevices)),
        });
      },
    );
    await page.goto('/');
    await expect(page.getByTestId('fleet-loading')).toBeVisible();
    await expect(page.getByTestId('summary-total')).toHaveText('3');
    await expect(page.getByTestId('fleet-loading')).toBeHidden();
  });

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

    await expect(page.getByText('No devices have been registered in the fleet yet.')).toBeVisible();
    await expect(page.getByTestId('summary-total')).toHaveText('0');
  });

  test('a 502 (Prometheus down) surfaces an error banner with retry', async ({ page }) => {
    await mockFleet(page, { detail: 'Prometheus query failed: boom' }, 502);
    await page.goto('/');

    await expect(page.getByText('Unable to load fleet data')).toBeVisible();
    await expect(page.getByText('Prometheus query failed: boom')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Retry' })).toBeVisible();
  });

  test('search filters devices by name or device id', async ({ page }) => {
    await mockFleet(page, fleetView(sampleDevices));
    await page.goto('/');

    const search = page.getByTestId('fleet-search').getByRole('textbox');
    await search.fill('jetson-00');
    await expect(page.getByTestId(/^device-title-/)).toHaveCount(1);

    await search.fill('jetson-02');
    await expect(page.getByTestId(/^device-title-/)).toHaveCount(1);

    await search.fill('no-match');
    await expect(page.getByText('No devices match the current filter.')).toBeVisible();
  });

  test('health filter shows only matching devices', async ({ page }) => {
    await mockFleet(page, fleetView(sampleDevices));
    await page.goto('/');

    const dropdown = page.getByTestId('fleet-health-filter').locator('.bx--list-box');
    await dropdown.click();
    await page.getByRole('option', { name: 'Offline' }).click();

    await expect(page.getByTestId(/^device-title-/)).toHaveCount(1);
    await expect(page.getByTestId('device-title-jetson-02')).toBeVisible();
  });

  test('sort changes device order', async ({ page }) => {
    await mockFleet(page, fleetView(sampleDevices));
    await page.goto('/');

    const titles = page.getByTestId(/^device-title-/);
    await expect(titles.first()).toContainText('jetson-00');

    const dropdown = page.getByTestId('fleet-sort').locator('.bx--list-box');
    await dropdown.click();
    await page.getByRole('option', { name: 'GPU % (high to low)' }).click();

    await expect(titles.first()).toContainText('jetson-00');
  });

  test('clicking Details navigates to the device detail page', async ({ page }) => {
    await mockFleet(page, fleetView(sampleDevices));
    await page.goto('/');

    await page.getByTestId('device-title-jetson-00').click();
    await page.getByTestId('device-body-jetson-00').getByRole('link', { name: 'Details' }).click();

    await expect(page).toHaveURL('/devices/jetson-00');
    await expect(page.getByRole('heading', { name: 'jetson-00' })).toBeVisible();
  });
});
