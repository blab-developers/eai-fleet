<script lang="ts">
	import { InlineNotification } from 'carbon-components-svelte';

	interface Props {
		/** Devices exist in the fleet, but none are currently visible. */
		filtered?: boolean;
		/** The emptiness is from an active search/health filter (vs all devices being demo-hidden). */
		byFilter?: boolean;
	}

	let { filtered = false, byFilter = false }: Props = $props();

	const title = $derived(!filtered ? 'No devices' : byFilter ? 'No matches' : 'No devices visible');
	const subtitle = $derived(
		!filtered
			? 'No devices have been registered in the fleet yet.'
			: byFilter
				? 'No devices match the current filter. Try clearing the search or changing the health filter.'
				: 'No devices are visible in the fleet. Demo devices are hidden — enable demo mode in Settings to show them.'
	);
</script>

<div data-testid="fleet-empty">
	<InlineNotification kind="info" {title} {subtitle} hideCloseButton />
</div>
