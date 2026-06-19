<script lang="ts">
	import { Button, Grid, Row, Column, Tile, Toggle } from 'carbon-components-svelte';
	import { Reset } from 'carbon-icons-svelte';
	import { preferences } from '$lib/preferences.svelte';
</script>

<h1 data-testid="settings-heading">Settings</h1>

<Grid>
	<Row>
		<Column sm={4} md={8} lg={8}>
			<Tile data-testid="demo-tile">
				<h2>Demo mode</h2>
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
				<h2>Local preferences</h2>
				<Button kind="tertiary" size="sm" icon={Reset} onclick={() => preferences.clear()}>
					Reset preferences
				</Button>
			</Tile>
		</Column>
	</Row>
</Grid>

<style lang="scss">
	h1 {
		font-size: var(--bx-productive-heading-03-font-size, 1.25rem);
		font-weight: 400;
		margin: 0 0 var(--bx-spacing-06);
	}
	h2 {
		font-size: var(--bx-productive-heading-02-font-size, 1rem);
		font-weight: 600;
		margin: 0 0 var(--bx-spacing-05);
	}
</style>
