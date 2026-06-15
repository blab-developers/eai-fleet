<script lang="ts">
	import { InlineNotification, NotificationActionButton, InlineLoading } from 'carbon-components-svelte';
	import { fleetStore } from '$lib/state.svelte';

	interface Props {
		message: string;
	}

	let { message }: Props = $props();
</script>

<InlineNotification
	kind="error"
	title="Unable to load fleet data"
	subtitle={message}
	hideCloseButton
>
	<svelte:fragment slot="actions">
		{#if fleetStore.isLoading}
			<InlineLoading status="active" description="Retrying..." />
		{:else}
			<NotificationActionButton onclick={() => fleetStore.retry()}>
				Retry
			</NotificationActionButton>
		{/if}
	</svelte:fragment>
</InlineNotification>
