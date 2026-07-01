<script lang="ts">
	/**
	 * The fleet's currently-running inference image (the "running version").
	 *
	 * Fleet-wide in v1 — one inference DaemonSet, one image — so this reads the single value
	 * the store polls (fleetStore.inferenceImage), not a per-device field. Shows "—" when the
	 * cluster read is unavailable (dev/demo without k8s), never a hard error.
	 */
	import { Tag } from 'carbon-components-svelte';
	import { fleetStore } from '$lib/state.svelte';
</script>

<p class="running-image" data-testid="running-image">
	<span class="label">Inference image</span>
	<Tag type="cool-gray" size="sm">fleet-wide</Tag>
	<code class="value">{fleetStore.inferenceImage ?? '—'}</code>
</p>

<style lang="scss">
	.running-image {
		display: flex;
		align-items: center;
		gap: var(--bx-spacing-03, 0.5rem);
		flex-wrap: wrap;
		margin: 0;
	}
	.label {
		font-size: var(--bx-label-01-font-size, 0.75rem);
		color: var(--bx-text-secondary);
	}
	.value {
		font-family: var(--bx-font-mono, monospace);
		font-size: var(--bx-body-compact-01-font-size, 0.875rem);
		color: var(--bx-text-primary);
		word-break: break-all;
	}
</style>
