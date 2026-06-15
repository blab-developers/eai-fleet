import { test, expect, mockSetImage, json } from '../common/fixtures';
import type { Page } from '@playwright/test';

const IMAGE = 'registry.endoscopeai.com/eai-nano/inference:v0.4.2';

async function openDevice(page: Page) {
  await page.goto('/');
  await page.getByTestId('device-title-jetson-00').click();
  const body = page.getByTestId('device-body-jetson-00');
  return { body, input: body.getByRole('textbox'), apply: body.getByRole('button', { name: 'Apply' }) };
}

test.describe('set inference image', () => {
  test('Apply is disabled until an image is typed', async ({ mockedPage }) => {
    const { input, apply } = await openDevice(mockedPage);
    await expect(apply).toBeDisabled();
    await input.fill(IMAGE);
    await expect(apply).toBeEnabled();
  });

  test('a successful set shows the success note and clears the input', async ({ mockedPage }) => {
    await mockSetImage(mockedPage, (route, id) =>
      route.fulfill(
        json(200, {
          device_id: id,
          image: IMAGE,
          scope: 'fleet-wide',
          note: 'Inference DaemonSet eai-nano/eai-nano-inference patched.',
        }),
      ),
    );
    const { body, input, apply } = await openDevice(mockedPage);
    await input.fill(IMAGE);
    await apply.click();

    await expect(body.getByText('Image set')).toBeVisible();
    await expect(body.getByText(/fleet-wide:/)).toBeVisible();
    await expect(input).toHaveValue('');
  });

  test('an unknown device (404) shows the error note', async ({ mockedPage }) => {
    await mockSetImage(mockedPage, (route, id) =>
      route.fulfill(json(404, { detail: `device '${id}' not in fleet` })),
    );
    const { body, input, apply } = await openDevice(mockedPage);
    await input.fill(IMAGE);
    await apply.click();

    await expect(body.getByText('Set image failed')).toBeVisible();
    await expect(body.getByText("device 'jetson-00' not in fleet")).toBeVisible();
  });

  test('a k8s failure (502) shows the error note', async ({ mockedPage }) => {
    await mockSetImage(mockedPage, (route) =>
      route.fulfill(json(502, { detail: 'k8s PATCH transport failed: apiserver down' })),
    );
    const { body, input, apply } = await openDevice(mockedPage);
    await input.fill(IMAGE);
    await apply.click();

    await expect(body.getByText('Set image failed')).toBeVisible();
    await expect(body.getByText(/apiserver down/)).toBeVisible();
  });
});
