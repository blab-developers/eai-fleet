<script lang="ts">
	import '../app.css';
	import 'carbon-components-svelte/css/g90.css';
	import { onMount, onDestroy } from 'svelte';
	import { Header, HeaderUtilities, HeaderGlobalAction, Content, Grid, Row, Column } from 'carbon-components-svelte';
	import { ChartLine, Settings } from 'carbon-icons-svelte';
	import { page } from '$app/state';
	import { env } from '$env/dynamic/public';
	import { fleetStore, POLL_MS } from '$lib/state.svelte';

	let { children } = $props();
	const grafanaUrl = env.EAI_FLEET_FRONTEND_GRAFANA_URL ?? '';

	let timer: ReturnType<typeof setInterval> | undefined;

	onMount(() => {
		fleetStore.loadFleet();
		fleetStore.loadInferenceImage();
		timer = setInterval(() => {
			fleetStore.loadFleet();
			fleetStore.loadInferenceImage();
		}, POLL_MS);
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
		<!-- Labeled action (gear + the word "Settings") rather than Carbon's bare icon-only
		     HeaderGlobalAction — the icon alone renders invisibly on the dark g90 header and gives
		     no text affordance. Uses Carbon's header-action classes (themed in app.css). -->
		<a
			href="/settings"
			class="bx--header__action settings-action"
			class:bx--header__action--active={page.url.pathname === '/settings'}
			aria-label="Settings"
			data-testid="settings-link"
		>
			<Settings size={20} />
			<span>Settings</span>
		</a>
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
