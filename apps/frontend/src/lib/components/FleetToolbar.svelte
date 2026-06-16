<script lang="ts">
	import { Grid, Row, Column, TextInput, Dropdown } from 'carbon-components-svelte';
	import { fleetStore } from '$lib/state.svelte';
	import { HEALTH_FILTER_OPTIONS, SORT_OPTIONS } from '$lib/models';
	import LastUpdated from './LastUpdated.svelte';

	const healthItems = HEALTH_FILTER_OPTIONS.map((opt) => ({ id: opt.value, text: opt.label }));
	const sortItems = SORT_OPTIONS.map((opt) => ({ id: opt.value, text: opt.label }));
</script>

<div data-testid="fleet-toolbar">
	<Grid class="toolbar-grid">
		<Row>
			<Column sm={4} md={4} lg={8}>
				<div data-testid="fleet-search">
					<TextInput
						size="sm"
						labelText="Search"
						placeholder="Filter by name or device ID"
						bind:value={fleetStore.searchQuery}
					/>
				</div>
			</Column>
			<Column sm={4} md={2} lg={4}>
				<div data-testid="fleet-health-filter">
					<Dropdown
						size="sm"
						titleText="Health"
						selectedId={fleetStore.healthFilter}
						items={healthItems}
						on:select={(e) => {
							fleetStore.healthFilter = e.detail.selectedId as typeof fleetStore.healthFilter;
						}}
					/>
				</div>
			</Column>
			<Column sm={4} md={2} lg={4}>
				<div data-testid="fleet-sort">
					<Dropdown
						size="sm"
						titleText="Sort by"
						selectedId={fleetStore.sortBy}
						items={sortItems}
						on:select={(e) => {
							fleetStore.sortBy = e.detail.selectedId as typeof fleetStore.sortBy;
						}}
					/>
				</div>
			</Column>
		</Row>
	</Grid>

	<Grid class="toolbar-meta-grid">
		<Row>
			<Column sm={2} md={4} lg={8}>
				<p class="showing" data-testid="showing-count">
					Showing {fleetStore.filteredTotal} of {fleetStore.total} devices
				</p>
			</Column>
			<Column sm={2} md={4} lg={8}>
				<p class="last-updated-wrapper">
					<LastUpdated timestamp={fleetStore.lastUpdated} />
				</p>
			</Column>
		</Row>
	</Grid>
</div>

<style lang="scss">
	.showing {
		font-size: var(--bx-label-01-font-size, 0.75rem);
		color: var(--bx-text-secondary);
		margin: var(--bx-spacing-03) 0 0;
	}
	.last-updated-wrapper {
		text-align: right;
		margin: var(--bx-spacing-03) 0 0;
	}
</style>
