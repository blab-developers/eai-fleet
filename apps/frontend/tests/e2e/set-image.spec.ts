import { test, expect, type Page } from '@playwright/test';
import { fleetView, json, mockFleet, mockSetImage, sampleDevices } from './mocks';

const IMAGE = 'registry.endoscopeai.com/eai-nano/inference:v0.4.2';

/** Open jetson-00's row and return its scoped body + controls. */
async function openDevice(page: Page) {
  await page.goto('/');
  await page.getByTestId('device-title-jetson-00').click();
  const body = page.getByTestId('device-body-jetson-00');
  return { body, input: body.getByRole('textbox'), apply: body.getByRole('button', { name: 'Apply' }) };
}

test.describe('set inference image', () => {
  test.beforeEach(async ({ page }) => {
    await mockFleet(page, fleetView(sampleDevices));
  });

  test('Apply is disabled until an image is typed', async ({ page }) => {
    const { input, apply } = await openDevice(page);
    await expect(apply).toBeDisabled();
    await input.fill(IMAGE);
    await expect(apply).toBeEnabled();
  });

  test('a successful set shows the success note and clears the input', async ({ page }) => {
    await mockSetImage(page, (route, id) =>
      route.fulfill(
        json(200, {
          device_id: id,
          image: IMAGE,
          scope: 'fleet-wide',
          note: 'Inference DaemonSet eai-nano/eai-nano-inference patched.',
        }),
      ),
    );
    const { body, input, apply } = await openDevice(page);
    await input.fill(IMAGE);
    await apply.click();

    await expect(body.getByText('Image set')).toBeVisible();
    await expect(body.getByText(/fleet-wide:/)).toBeVisible();
    await expect(input).toHaveValue('');
  });

  test('an unknown device (404) shows the error note', async ({ page }) => {
    await mockSetImage(page, (route, id) =>
      route.fulfill(json(404, { detail: `device '${id}' not in fleet` })),
    );
    const { body, input, apply } = await openDevice(page);
    await input.fill(IMAGE);
    await apply.click();

    await expect(body.getByText('Set image failed')).toBeVisible();
    await expect(body.getByText("device 'jetson-00' not in fleet")).toBeVisible();
  });

  test('a k8s failure (502) shows the error note', async ({ page }) => {
    await mockSetImage(page, (route) =>
      route.fulfill(json(502, { detail: 'k8s PATCH transport failed: apiserver down' })),
    );
    const { body, input, apply } = await openDevice(page);
    await input.fill(IMAGE);
    await apply.click();

    await expect(body.getByText('Set image failed')).toBeVisible();
    await expect(body.getByText(/apiserver down/)).toBeVisible();
  });
});
