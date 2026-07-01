<script lang="ts">
	/**
	 * Model selector + deploy: pick one of the catalog's model versions and push its package
	 * to a nano backend.
	 *
	 * "All available models" (fleetStore.models) is read live from eai-catalog via the backend.
	 * The deploy targets THIS device, but the fleet is stateless (Spec 008 — no device→URL map),
	 * so the nano's reachable base URL (+ optional token) is caller-supplied here. The Deploy
	 * button drives the existing POST /devices/{id}/models/{version}/deploy endpoint.
	 */
	import {
		Dropdown,
		TextInput,
		PasswordInput,
		Button,
		InlineNotification
	} from 'carbon-components-svelte';
	import { deployModelPackage } from '$lib/generated/fleet-backend-api';
	import { getErrorMessage } from '$lib/errors';
	import { fleetStore } from '$lib/state.svelte';

	interface Props {
		deviceId: string;
	}

	let { deviceId }: Props = $props();

	// Carbon Dropdown items — id is the model_version_id the deploy route takes; text labels
	// the option (name, plus the Jetson target when the catalog records one).
	const items = $derived(
		fleetStore.models.map((m) => ({
			id: m.id,
			text: m.jetson_device_target ? `${m.name} · ${m.jetson_device_target}` : m.name
		}))
	);

	let selectedId = $state<string | null>(null);
	let nanoBaseUrl = $state('');
	let nanoToken = $state('');
	let busy = $state(false);
	let note = $state<string | null>(null);
	let error = $state<string | null>(null);

	const canDeploy = $derived(!!selectedId && nanoBaseUrl.trim().length > 0 && !busy);

	async function handleSubmit(event: Event): Promise<void> {
		event.preventDefault();
		if (!selectedId || !nanoBaseUrl.trim()) return;
		busy = true;
		note = null;
		error = null;
		try {
			const { data, error: apiError } = await deployModelPackage({
				path: { device_id: deviceId, model_version_id: selectedId },
				body: { nano_base_url: nanoBaseUrl.trim(), nano_token: nanoToken.trim() }
			});
			if (data) {
				note = `Deployed model ${data.model_id} to ${deviceId} (nano model ${data.nano_model_id}).`;
			} else {
				error = getErrorMessage(apiError);
			}
		} catch (e) {
			error = getErrorMessage(e);
		} finally {
			busy = false;
		}
	}
</script>

<form onsubmit={handleSubmit} data-testid="model-deploy-form-{deviceId}">
	{#if fleetStore.modelsLoaded && fleetStore.models.length === 0}
		<InlineNotification
			kind="info"
			lowContrast
			hideCloseButton
			title="No models available"
			subtitle={fleetStore.modelsError ?? 'The catalog has no model versions to deploy.'}
		/>
	{:else}
		<Dropdown
			titleText="Model"
			label="Select a model…"
			{items}
			selectedId={selectedId ?? undefined}
			disabled={busy || items.length === 0}
			data-testid="model-dropdown-{deviceId}"
			on:select={(e) => (selectedId = String(e.detail.selectedId))}
		/>
		<div class="nano-fields">
			<!-- data-testid on wrappers: Carbon input types don't accept arbitrary HTML attrs. -->
			<div data-testid="nano-url-{deviceId}">
				<TextInput
					size="sm"
					labelText="Nano base URL"
					placeholder="http://<nano-host>:8000"
					helperText="The reachable eai-nano backend to install the package on."
					bind:value={nanoBaseUrl}
				/>
			</div>
			<div data-testid="nano-token-{deviceId}">
				<PasswordInput
					size="sm"
					labelText="Nano token (optional)"
					placeholder="Bearer token, if the nano requires one"
					bind:value={nanoToken}
				/>
			</div>
		</div>
		<Button size="sm" type="submit" disabled={!canDeploy} data-testid="deploy-btn-{deviceId}">
			Deploy model
		</Button>
	{/if}
</form>

{#if note}
	<InlineNotification kind="success" title="Model deployed" subtitle={note} lowContrast />
{/if}
{#if error}
	<InlineNotification kind="error" title="Deploy failed" subtitle={error} lowContrast />
{/if}

<style lang="scss">
	.nano-fields {
		display: flex;
		gap: var(--bx-spacing-05, 1rem);
		flex-wrap: wrap;
		margin: var(--bx-spacing-05, 1rem) 0;
	}
	.nano-fields > :global(*) {
		flex: 1 1 240px;
	}
</style>
