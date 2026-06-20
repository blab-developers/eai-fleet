import { describe, it, expect } from 'vitest';
import { render } from 'vitest-browser-svelte';
import { page } from 'vitest/browser';
import EmptyState from '$lib/components/EmptyState.svelte';

// The component is ALL $derived (title/subtitle computed from `filtered`/`byFilter`). happy-dom +
// @testing-library mis-handle Svelte-5 runes, so this is exactly the case the real-browser tier
// exists for: render each prop combination and assert the derived copy that actually paints.
describe('EmptyState (browser) — $derived title/subtitle across prop combos', () => {
	it('defaults to the empty-fleet message', async () => {
		render(EmptyState, {});
		await expect.element(page.getByText('No devices')).toBeInTheDocument();
		await expect.element(page.getByText(/No devices have been registered/)).toBeInTheDocument();
	});

	it('shows the no-matches message when an active search/health filter hides everything', async () => {
		render(EmptyState, { filtered: true, byFilter: true });
		await expect.element(page.getByText('No matches')).toBeInTheDocument();
		await expect.element(page.getByText(/No devices match the current filter/)).toBeInTheDocument();
	});

	it('shows the demo-hidden message when filtered but not by a filter', async () => {
		render(EmptyState, { filtered: true, byFilter: false });
		await expect.element(page.getByText('No devices visible')).toBeInTheDocument();
		await expect.element(page.getByText(/Demo devices are hidden/)).toBeInTheDocument();
	});
});
