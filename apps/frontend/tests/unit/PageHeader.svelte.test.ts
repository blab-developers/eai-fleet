import { describe, it, expect } from 'vitest';
import { render } from 'vitest-browser-svelte';
import { page } from 'vitest/browser';
import PageHeader from '$lib/components/PageHeader.svelte';

// Real-browser render of the shared page header — the title is a heading, the description is
// optional. A pure-logic ($lib) test could not prove either; that is the point of this tier.
describe('PageHeader (browser)', () => {
	it('renders the title as a heading and shows the description when given', async () => {
		render(PageHeader, { title: 'Fleet', description: 'All registered devices' });
		await expect.element(page.getByRole('heading', { name: 'Fleet' })).toBeInTheDocument();
		await expect.element(page.getByText('All registered devices')).toBeInTheDocument();
	});

	it('omits the description paragraph when none is provided', async () => {
		render(PageHeader, { title: 'Settings' });
		await expect.element(page.getByRole('heading', { name: 'Settings' })).toBeInTheDocument();
		expect(page.getByText('All registered devices').query()).toBeNull();
	});
});
