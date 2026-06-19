import { test, expect, mockFleet, fleetView, demoDevices } from '../common/fixtures';

test.describe('settings', () => {
  test('header settings action opens Settings', async ({ mockedPage }) => {
    await mockedPage.goto('/');

    await mockedPage.getByTestId('settings-link').click();

    await expect(mockedPage).toHaveURL('/settings');
    await expect(mockedPage.getByTestId('settings-heading')).toBeVisible();
  });

  test('demo toggle hides backend-marked demo devices', async ({ page }) => {
    await mockFleet(page, fleetView(demoDevices));
    await page.goto('/');

    await expect(page.getByTestId('summary-total')).toHaveText('3');

    await page.getByTestId('settings-link').click();
    await page.getByRole('switch', { name: 'Show demo devices' }).click();
    await page.goto('/');

    await expect(page.getByText('No devices are visible in the fleet.')).toBeVisible();
    await expect(page.getByTestId('summary-total')).toHaveText('0');
  });
});
