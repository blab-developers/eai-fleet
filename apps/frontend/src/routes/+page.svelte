<script lang="ts">
	import { Accordion } from 'carbon-components-svelte';
	import { fleetStore } from '$lib/state.svelte';
	import FleetSummary from '$lib/components/FleetSummary.svelte';
	import RunningImage from '$lib/components/RunningImage.svelte';
	import FleetToolbar from '$lib/components/FleetToolbar.svelte';
	import DeviceAccordionItem from '$lib/components/DeviceAccordionItem.svelte';
	import EmptyState from '$lib/components/EmptyState.svelte';
	import ErrorRetry from '$lib/components/ErrorRetry.svelte';
	import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';
</script>

<h1>Fleet</h1>

{#if !fleetStore.loaded}
	<LoadingSkeleton />
{:else if fleetStore.error}
	<ErrorRetry message={fleetStore.error} />
{:else}
	<FleetSummary
		total={fleetStore.filteredTotal}
		online={fleetStore.filteredOnline}
		offline={fleetStore.filteredOffline}
	/>

	<div class="running-image-wrapper">
		<RunningImage />
	</div>

	{#if fleetStore.total > 0}
		<div class="toolbar-wrapper">
			<FleetToolbar />
		</div>
	{/if}

	{#if fleetStore.filteredDevices.length === 0}
		<EmptyState filtered={fleetStore.total > 0} byFilter={fleetStore.hasActiveFilter} />
	{:else}
		<Accordion>
			{#each fleetStore.filteredDevices as device (device.device_id)}
				<DeviceAccordionItem {device} />
			{/each}
		</Accordion>
	{/if}
{/if}

<style lang="scss">
	h1 {
		font-size: var(--bx-productive-heading-03-font-size, 1.25rem);
		font-weight: 400;
		margin: 0 0 var(--bx-spacing-06);
	}
	.toolbar-wrapper {
		margin-bottom: var(--bx-spacing-06);
	}
	.running-image-wrapper {
		margin: 0 0 var(--bx-spacing-06);
	}
</style>
