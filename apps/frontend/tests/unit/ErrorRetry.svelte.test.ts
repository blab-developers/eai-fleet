import { describe, it, expect, vi } from 'vitest';
import { render } from 'vitest-browser-svelte';
import { page } from 'vitest/browser';
import ErrorRetry from '$lib/components/ErrorRetry.svelte';

// Own ONE thing: the error notification's rendered behaviour + that Retry drives the store. The
// store itself is unit-tested in tests/unit/state.test.ts, so mock the single $lib seam (mirrors
// eai-nano's DeletePatientModal test). The not-loading branch shows the Retry button.
const { retryMock } = vi.hoisted(() => ({ retryMock: vi.fn() }));
vi.mock('$lib/state.svelte', () => ({ fleetStore: { isLoading: false, retry: retryMock } }));

describe('ErrorRetry (browser)', () => {
	it('shows the message and calls fleetStore.retry() when Retry is clicked', async () => {
		render(ErrorRetry, { message: 'Backend unreachable' });

		await expect.element(page.getByText('Unable to load fleet data')).toBeInTheDocument();
		await expect.element(page.getByText('Backend unreachable')).toBeInTheDocument();

		await page.getByRole('button', { name: 'Retry' }).click();
		expect(retryMock).toHaveBeenCalledOnce();
	});
});
