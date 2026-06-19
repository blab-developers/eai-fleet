<script lang="ts">
	import { Button, Grid, Row, Column, Tile, Toggle } from 'carbon-components-svelte';
	import { Reset } from 'carbon-icons-svelte';
	import { preferences } from '$lib/preferences.svelte';
	import PageHeader from '$lib/components/PageHeader.svelte';
</script>

<PageHeader
	title="Settings"
	description="Fleet view preferences for this browser."
	testid="settings-heading"
/>

<Grid>
	<Row>
		<Column sm={4} md={8} lg={8}>
			<Tile data-testid="demo-tile">
				<h3 class="tile-heading">Demo mode</h3>
				<p class="muted spaced">
					Shows clearly-fake demo devices in the fleet view (on by default). Turn it off to hide
					them and see only real devices.
				</p>
				<Toggle
					labelText="Show demo devices"
					labelA="off"
					labelB="on"
					toggled={preferences.demoMode}
					data-testid="demo-mode-toggle"
					on:toggle={(e) => (preferences.demoMode = e.detail.toggled)}
				/>
			</Tile>
		</Column>
		<Column sm={4} md={8} lg={8}>
			<Tile data-testid="preferences-tile">
				<h3 class="tile-heading">Local preferences</h3>
				<p class="muted spaced">
					Per-browser settings stored on this device only. Resetting restores the defaults
					(demo devices shown).
				</p>
				<Button kind="tertiary" size="sm" icon={Reset} onclick={() => preferences.clear()}>
					Reset preferences
				</Button>
			</Tile>
		</Column>
	</Row>
</Grid>

<style>
	/* Mirrors eai-nano's settings tile idiom (tile-heading + muted/spaced), Carbon design tokens. */
	.muted {
		color: var(--cds-text-secondary);
		font-size: var(--bx-body-long-01-font-size, 0.875rem);
	}
	.spaced {
		margin-bottom: var(--bx-spacing-05, 1rem);
	}
	.tile-heading {
		margin: 0 0 var(--bx-spacing-05, 1rem);
		font-size: var(--bx-productive-heading-02-font-size, 1rem);
		font-weight: 600;
		color: var(--cds-text-primary);
	}
</style>
