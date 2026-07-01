<script lang="ts">
	import { page } from '$app/state';
	import {
		Button,
		ButtonSet,
		Tag,
		Loading,
		InlineNotification,
		Grid,
		Row,
		Column,
		Tile,
	} from 'carbon-components-svelte';
	import { ArrowLeft, ChartLine } from 'carbon-icons-svelte';
	import { env } from '$env/dynamic/public';
	import { fleetStore } from '$lib/state.svelte';
	import SetImageForm from '$lib/components/SetImageForm.svelte';
	import RunningImage from '$lib/components/RunningImage.svelte';
	import DeviceInferenceActions from '$lib/components/DeviceInferenceActions.svelte';
	import ModelDeployForm from '$lib/components/ModelDeployForm.svelte';

	const grafanaBase = env.EAI_FLEET_FRONTEND_GRAFANA_URL ?? '';
	const deviceId = $derived(page.params.device_id);
	const device = $derived(fleetStore.devices.find((d) => d.device_id === deviceId));
	const online = $derived(device?.health === 'online');

	const grafanaLink = $derived(
		device && grafanaBase
			? `${grafanaBase}${grafanaBase.includes('?') ? '&' : '?'}var-device=${encodeURIComponent(device.device_id)}`
			: ''
	);
</script>

<Button kind="ghost" size="sm" icon={ArrowLeft} href="/">Back to fleet</Button>

{#if !fleetStore.loaded}
	<div class="state-wrapper">
		<Loading withOverlay={false} />
	</div>
{:else if fleetStore.error}
	<InlineNotification kind="error" title="Fleet view unavailable" subtitle={fleetStore.error} hideCloseButton />
{:else if !device}
	<InlineNotification
		kind="warning"
		title="Device not found"
		subtitle="No device with ID {deviceId} is currently in the fleet."
		hideCloseButton
	/>
{:else}
	<h1>{device.name}</h1>
	<p class="subtitle">
		<Tag type={online ? 'green' : 'red'} size="sm">{device.health}</Tag>
		<span class="device-id">{device.device_id}</span>
	</p>

	<Grid>
		<Row>
			<Column sm={4} md={4} lg={4}>
				<Tile>
					<p class="metric-label">State</p>
					<p class="metric-value">{device.state}</p>
				</Tile>
			</Column>
			<Column sm={4} md={4} lg={4}>
				<Tile>
					<p class="metric-label">FPS</p>
					<p class="metric-value">{device.fps.toFixed(1)}</p>
				</Tile>
			</Column>
			<Column sm={4} md={4} lg={4}>
				<Tile>
					<p class="metric-label">GPU utilization</p>
					<p class="metric-value">{device.gpu_utilization.toFixed(0)}%</p>
				</Tile>
			</Column>
			<Column sm={4} md={4} lg={4}>
				<Tile>
					<p class="metric-label">Kiosk</p>
					<p class="metric-value" data-testid="metric-detail-kiosk">
						{#if device.chromium_running === true}
							<Tag type="green" size="sm">active</Tag>
						{:else if device.chromium_running === false}
							<Tag type="red" size="sm">down</Tag>
						{:else}
							<Tag type="gray" size="sm">--</Tag>
						{/if}
					</p>
				</Tile>
			</Column>
		</Row>
	</Grid>

	<ButtonSet class="detail-actions">
		{#if grafanaBase}
			<Button kind="ghost" size="sm" icon={ChartLine} href={grafanaLink} target="_blank">
				History
			</Button>
		{/if}
	</ButtonSet>

	<div class="running-image-detail">
		<RunningImage />
	</div>

	<h2>Deploy model</h2>
	<ModelDeployForm deviceId={device.device_id} />

	<h2>Set inference image</h2>
	<SetImageForm deviceId={device.device_id} />

	<h2>Operations</h2>
	<DeviceInferenceActions deviceId={device.device_id} />
{/if}

<style lang="scss">
	h1 {
		font-size: var(--bx-productive-heading-04-font-size, 1.75rem);
		font-weight: 400;
		margin: var(--bx-spacing-06) 0 var(--bx-spacing-03);
	}
	h2 {
		font-size: var(--bx-productive-heading-02-font-size, 1rem);
		font-weight: 600;
		margin: var(--bx-spacing-06) 0 var(--bx-spacing-03);
	}
	.subtitle > :global(*) {
		margin-right: var(--bx-spacing-04);
	}
	.device-id {
		font-size: var(--bx-body-compact-01-font-size, 0.875rem);
		color: var(--bx-text-secondary);
		font-family: var(--bx-font-mono, monospace);
	}
	.metric-label {
		font-size: var(--bx-label-01-font-size, 0.75rem);
		color: var(--bx-text-secondary);
		margin: 0 0 var(--bx-spacing-03);
	}
	.metric-value {
		font-size: var(--bx-productive-heading-04-font-size, 1.75rem);
		font-weight: 600;
		color: var(--bx-text-primary);
		margin: 0;
	}
	.state-wrapper {
		padding: var(--bx-spacing-09) 0;
	}
	.running-image-detail {
		margin: var(--bx-spacing-05) 0 0;
	}
</style>
