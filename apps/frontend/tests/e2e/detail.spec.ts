import { test, expect } from '@playwright/test';
import { fleetView, mockFleet, sampleDevices } from './mocks';

test.describe('device detail', () => {
  test('shows device metrics and a back link', async ({ page }) => {
    await mockFleet(page, fleetView(sampleDevices));
    await page.goto('/devices/jetson-00');

    await expect(page.getByRole('heading', { name: 'jetson-00' })).toBeVisible();
    await expect(page.getByText('running')).toBeVisible();
    await expect(page.getByText('29.5')).toBeVisible();
    await expect(page.getByRole('link', { name: 'Back to fleet' })).toHaveAttribute('href', '/');
  });

  test('shows not found for an unknown device', async ({ page }) => {
    await mockFleet(page, fleetView(sampleDevices));
    await page.goto('/devices/unknown');

    await expect(page.getByText('Device not found')).toBeVisible();
    await expect(page.getByText("No device with ID unknown is currently in the fleet.")).toBeVisible();
  });

  test('back link returns to the fleet list', async ({ page }) => {
    await mockFleet(page, fleetView(sampleDevices));
    await page.goto('/devices/jetson-00');

    await page.getByRole('link', { name: 'Back to fleet' }).click();
    await expect(page).toHaveURL('/');
    await expect(page.getByTestId('summary-total')).toHaveText('3');
  });
});
