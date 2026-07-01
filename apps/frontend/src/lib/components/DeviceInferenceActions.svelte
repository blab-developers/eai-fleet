<script lang="ts">
	/**
	 * Restart + Rollback controls for the inference workload, behind a confirm modal.
	 *
	 * Both are fleet-wide-under-a-per-device-shape in v1 (the inference workload is a single
	 * DaemonSet), so the confirm copy is explicit that the action hits EVERY nano — same shape
	 * as SetImageForm. Restart = rollout-restart; Rollback = revert to the previous image.
	 */
	import { Button, Modal, InlineNotification } from 'carbon-components-svelte';
	import { Restart, Reset } from 'carbon-icons-svelte';
	import { restartInference, rollbackInference } from '$lib/generated/fleet-backend-api';
	import { getErrorMessage } from '$lib/errors';
	import { fleetStore } from '$lib/state.svelte';

	interface Props {
		deviceId: string;
	}

	let { deviceId }: Props = $props();

	type Op = 'restart' | 'rollback';

	const COPY: Record<Op, { heading: string; primary: string; body: string }> = {
		restart: {
			heading: 'Restart inference',
			primary: 'Restart',
			body: 'This rolls (restarts) the inference pods. In v1 it affects EVERY nano in the fleet, not just this device — live sessions will briefly drop.'
		},
		rollback: {
			heading: 'Roll back inference image',
			primary: 'Roll back',
			body: 'This reverts the inference image to its previous deployed version. In v1 it affects EVERY nano in the fleet.'
		}
	};

	let activeOp = $state<Op | null>(null);
	let busy = $state(false);
	let note = $state<string | null>(null);
	let error = $state<string | null>(null);

	async function confirm(): Promise<void> {
		const op = activeOp;
		if (!op) return;
		busy = true;
		note = null;
		error = null;
		try {
			const { data, error: apiError } =
				op === 'restart'
					? await restartInference({ path: { device_id: deviceId } })
					: await rollbackInference({ path: { device_id: deviceId } });
			if (data) {
				note = data.note;
				// A rollback changes the running image — refresh the displayed version.
				if (op === 'rollback') void fleetStore.loadInferenceImage();
			} else {
				error = getErrorMessage(apiError);
			}
		} catch (e) {
			error = getErrorMessage(e);
		} finally {
			busy = false;
			activeOp = null;
		}
	}
</script>

<div class="ops" data-testid="device-ops-{deviceId}">
	<Button
		kind="tertiary"
		size="sm"
		icon={Restart}
		disabled={busy}
		data-testid="restart-btn-{deviceId}"
		onclick={() => (activeOp = 'restart')}
	>
		Restart
	</Button>
	<Button
		kind="tertiary"
		size="sm"
		icon={Reset}
		disabled={busy}
		data-testid="rollback-btn-{deviceId}"
		onclick={() => (activeOp = 'rollback')}
	>
		Rollback
	</Button>
</div>

{#if activeOp}
	<Modal
		danger
		open
		modalHeading={COPY[activeOp].heading}
		primaryButtonText={COPY[activeOp].primary}
		secondaryButtonText="Cancel"
		primaryButtonDisabled={busy}
		data-testid="confirm-{activeOp}-{deviceId}"
		on:click:button--secondary={() => (activeOp = null)}
		on:close={() => (activeOp = null)}
		on:submit={confirm}
	>
		<p>{COPY[activeOp].body}</p>
	</Modal>
{/if}

{#if note}
	<InlineNotification kind="success" title="Done" subtitle={note} lowContrast />
{/if}
{#if error}
	<InlineNotification kind="error" title="Operation failed" subtitle={error} lowContrast />
{/if}

<style lang="scss">
	.ops {
		display: flex;
		gap: var(--bx-spacing-03, 0.5rem);
		flex-wrap: wrap;
	}
</style>
