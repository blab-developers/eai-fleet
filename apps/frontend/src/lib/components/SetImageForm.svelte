<script lang="ts">
	import { Grid, Row, Column, TextInput, Button, InlineNotification } from 'carbon-components-svelte';
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

	const trimmed = $derived(image.trim());
	const valid = $derived(isValidImageTag(trimmed));

	async function handleSubmit(event: Event): Promise<void> {
		event.preventDefault();
		if (!trimmed || !valid) return;
		busy = true;
		note = null;
		error = null;
		try {
			const { data, error: apiError } = await setInferenceImage({
				path: { device_id: deviceId },
				body: { image: trimmed },
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
					disabled={busy || !valid}
				>
					Apply
				</Button>
			</Column>
		</Row>
	</Grid>
</form>

{#if note}
	<InlineNotification kind="success" title="Image set" subtitle={note} lowContrast />
{/if}
{#if error}
	<InlineNotification kind="error" title="Set image failed" subtitle={error} lowContrast />
{/if}
