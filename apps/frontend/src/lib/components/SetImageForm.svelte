<script lang="ts">
	import {
		Grid,
		Row,
		Column,
		TextInput,
		PasswordInput,
		Button,
		InlineNotification,
		Toggle
	} from 'carbon-components-svelte';
	import { setInferenceImage } from '$lib/generated/fleet-backend-api';
	import { getErrorMessage } from '$lib/errors';
	import { isValidImageTag } from '$lib/models';

	interface Props {
		deviceId: string;
	}

	let { deviceId }: Props = $props();

	let image = $state('');
	let busy = $state(false);
	let note = $state<string | null>(null);
	let error = $state<string | null>(null);

	// Optional coordinated shutdown: when enabled + a nano URL is given, the backend drains
	// that nano (finalize recording, stop pipeline) and requires confirmation BEFORE patching
	// the image — so an image swap never drops a recording.
	let coordinate = $state(false);
	let nanoBaseUrl = $state('');
	let nanoToken = $state('');

	const trimmed = $derived(image.trim());
	const valid = $derived(isValidImageTag(trimmed));
	// If coordination is on, a nano URL is required before Apply is allowed.
	const coordinationReady = $derived(!coordinate || nanoBaseUrl.trim().length > 0);

	async function handleSubmit(event: Event): Promise<void> {
		event.preventDefault();
		if (!trimmed || !valid || !coordinationReady) return;
		busy = true;
		note = null;
		error = null;
		try {
			const useCoordination = coordinate && nanoBaseUrl.trim().length > 0;
			const { data, error: apiError } = await setInferenceImage({
				path: { device_id: deviceId },
				body: {
					image: trimmed,
					...(useCoordination
						? { nano_base_url: nanoBaseUrl.trim(), nano_token: nanoToken.trim() }
						: {}),
				},
			});
			if (data) {
				note = `${data.scope}: ${data.note}`;
				image = '';
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

<form onsubmit={handleSubmit} data-testid="set-image-form-{deviceId}">
	<Grid noGutter>
		<Row>
			<Column sm={4} md={6} lg={12}>
				<TextInput
					size="sm"
					labelText="Container image"
					placeholder="registry.endoscopeai.com/eai-nano/inference:vX.Y.Z"
					invalid={trimmed.length > 0 && !valid}
					invalidText="Enter a valid container image reference"
					bind:value={image}
				/>
			</Column>
			<Column sm={4} md={2} lg={4}>
				<Button
					size="sm"
					type="submit"
					disabled={busy || !valid || !coordinationReady}
				>
					Apply
				</Button>
			</Column>
		</Row>
	</Grid>

	<div class="coordinate">
		<Toggle
			size="sm"
			labelText="Coordinate shutdown before change"
			labelA="off"
			labelB="on"
			toggled={coordinate}
			data-testid="coordinate-toggle-{deviceId}"
			on:toggle={(e) => (coordinate = e.detail.toggled)}
		/>
		{#if coordinate}
			<p class="hint">
				The nano is drained (any in-progress recording is finalized, pipeline stopped) and must
				confirm before the image is patched — so no recording is lost. Requires a reachable nano URL.
			</p>
			<div class="nano-fields">
				<div data-testid="coordinate-url-{deviceId}">
					<TextInput
						size="sm"
						labelText="Nano base URL"
						placeholder="http://<nano-host>:8000"
						bind:value={nanoBaseUrl}
					/>
				</div>
				<div data-testid="coordinate-token-{deviceId}">
					<PasswordInput
						size="sm"
						labelText="Nano token (optional)"
						placeholder="Bearer token, if the nano requires one"
						bind:value={nanoToken}
					/>
				</div>
			</div>
		{/if}
	</div>
</form>

{#if note}
	<InlineNotification kind="success" title="Image set" subtitle={note} lowContrast />
{/if}
{#if error}
	<InlineNotification kind="error" title="Set image failed" subtitle={error} lowContrast />
{/if}

<style lang="scss">
	.coordinate {
		margin-top: var(--bx-spacing-05, 1rem);
	}
	.hint {
		font-size: var(--bx-label-01-font-size, 0.75rem);
		color: var(--cds-text-secondary, #666);
		margin: var(--bx-spacing-03, 0.5rem) 0;
		max-width: 44rem;
	}
	.nano-fields {
		display: flex;
		gap: var(--bx-spacing-05, 1rem);
		flex-wrap: wrap;
	}
	.nano-fields > :global(*) {
		flex: 1 1 240px;
	}
</style>

