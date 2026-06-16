<script lang="ts">
	import '../app.css';
	import 'carbon-components-svelte/css/g90.css';
	import { onMount, onDestroy } from 'svelte';
	import { Header, HeaderUtilities, HeaderGlobalAction, Content, Grid, Row, Column } from 'carbon-components-svelte';
	import { ChartLine } from 'carbon-icons-svelte';
	import { env } from '$env/dynamic/public';
	import { fleetStore, POLL_MS } from '$lib/state.svelte';

	let { children } = $props();
	const grafanaUrl = env.EAI_FLEET_FRONTEND_GRAFANA_URL ?? '';

	let timer: ReturnType<typeof setInterval> | undefined;

	onMount(() => {
		fleetStore.loadFleet();
		timer = setInterval(() => fleetStore.loadFleet(), POLL_MS);
	});

	onDestroy(() => {
		if (timer) clearInterval(timer);
	});
</script>

<Header company="EAI" platformName="Fleet">
	<HeaderUtilities>
		{#if grafanaUrl}
			<HeaderGlobalAction
				icon={ChartLine}
				aria-label="Open Grafana dashboard"
				title="Open Grafana dashboard"
				onclick={() => window.open(grafanaUrl, '_blank', 'noopener,noreferrer')}
			/>
		{/if}
	</HeaderUtilities>
</Header>

<Content>
	<Grid>
		<Row>
			<Column>
				{@render children()}
			</Column>
		</Row>
	</Grid>
</Content>
