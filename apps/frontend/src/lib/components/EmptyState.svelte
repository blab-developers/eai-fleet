<script lang="ts">
	import { InlineNotification } from 'carbon-components-svelte';

	interface Props {
		filtered?: boolean;
	}

	let { filtered = false }: Props = $props();
</script>

<div data-testid="fleet-empty">
	<InlineNotification
		kind="info"
		title={filtered ? 'No matches' : 'No devices'}
		subtitle={filtered
			? 'No devices match the current filter. Try clearing the search or changing the health filter.'
			: 'No devices have been registered in the fleet yet.'}
		hideCloseButton
	/>
</div>
