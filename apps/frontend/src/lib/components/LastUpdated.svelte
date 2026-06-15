<script lang="ts">
	interface Props {
		timestamp: Date | null;
	}

	let { timestamp }: Props = $props();

	function formatTime(date: Date): string {
		return date.toLocaleTimeString(undefined, {
			hour: '2-digit',
			minute: '2-digit',
			second: '2-digit',
		});
	}
</script>

{#if timestamp}
	<span data-testid="last-updated">
		Last updated: {formatTime(timestamp)}
	</span>
{/if}
