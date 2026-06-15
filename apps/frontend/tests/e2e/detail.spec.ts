import { test, expect } from '../common/fixtures';

test.describe('device detail', () => {
  test('shows device metrics and a back link', async ({ mockedPage }) => {
    await mockedPage.goto('/devices/jetson-00');

    await expect(mockedPage.getByRole('heading', { name: 'jetson-00' })).toBeVisible();
    await expect(mockedPage.getByText('running')).toBeVisible();
    await expect(mockedPage.getByText('29.5')).toBeVisible();
    await expect(mockedPage.getByRole('link', { name: 'Back to fleet' })).toHaveAttribute('href', '/');
  });

  test('shows not found for an unknown device', async ({ mockedPage }) => {
    await mockedPage.goto('/devices/unknown');

    await expect(mockedPage.getByText('Device not found')).toBeVisible();
    await expect(mockedPage.getByText('No device with ID unknown is currently in the fleet.')).toBeVisible();
  });

  test('back link returns to the fleet list', async ({ mockedPage }) => {
    await mockedPage.goto('/devices/jetson-00');

    await mockedPage.getByRole('link', { name: 'Back to fleet' }).click();
    await expect(mockedPage).toHaveURL('/');
    await expect(mockedPage.getByTestId('summary-total')).toHaveText('3');
  });
});
