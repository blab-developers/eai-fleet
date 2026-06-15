<script lang="ts">
	import { AccordionItem, Tag, Button, ButtonSet, Tile, Grid, Row, Column } from 'carbon-components-svelte';
	import { ChartLine, ArrowRight } from 'carbon-icons-svelte';
	import { env } from '$env/dynamic/public';
	import type { DeviceView } from '$lib/generated/fleet-backend-api';
	import SetImageForm from './SetImageForm.svelte';

	interface Props {
		device: DeviceView;
	}

	let { device }: Props = $props();

	const grafanaBase = env.EAI_FLEET_FRONTEND_GRAFANA_URL ?? '';
	const online = $derived(device.health === 'online');

	function grafanaLink(deviceId: string): string {
		if (!grafanaBase) return '';
		const sep = grafanaBase.includes('?') ? '&' : '?';
		return `${grafanaBase}${sep}var-device=${encodeURIComponent(deviceId)}`;
	}
</script>

<AccordionItem>
	<span slot="title" class="row-title" data-testid="device-title-{device.device_id}">
		<span class="device-name">{device.name}</span>
		<Tag type={online ? 'green' : 'red'} size="sm">{device.health}</Tag>
		<span class="device-fps">{device.fps.toFixed(1)} fps</span>
	</span>

	<div class="device-body" data-testid="device-body-{device.device_id}">
		<Tile>
			<Grid noGutter>
				<Row>
					<Column sm={2} md={2} lg={4}>
						<p class="metric-label">State</p>
						<p class="metric-value" data-testid="metric-state">{device.state}</p>
					</Column>
					<Column sm={2} md={2} lg={4}>
						<p class="metric-label">FPS</p>
						<p class="metric-value" data-testid="metric-fps">{device.fps.toFixed(1)}</p>
					</Column>
					<Column sm={2} md={2} lg={4}>
						<p class="metric-label">GPU</p>
						<p class="metric-value" data-testid="metric-gpu">{device.gpu_utilization.toFixed(0)}%</p>
					</Column>
					<Column sm={2} md={2} lg={4}>
						<p class="metric-label">Health</p>
						<p class="metric-value" data-testid="metric-health">{device.health}</p>
					</Column>
				</Row>
			</Grid>
		</Tile>

		<ButtonSet class="device-actions">
			{#if grafanaBase}
				<Button
					kind="ghost"
					size="sm"
					icon={ChartLine}
					href={grafanaLink(device.device_id)}
					target="_blank"
				>
					History
				</Button>
			{/if}
			<Button kind="ghost" size="sm" icon={ArrowRight} href="/devices/{device.device_id}">
				Details
			</Button>
		</ButtonSet>

		<SetImageForm deviceId={device.device_id} />
	</div>
</AccordionItem>

<style lang="scss">
	.row-title > :global(*) {
		margin-right: var(--bx-spacing-04);
	}
	.device-name {
		font-weight: 600;
	}
	.device-fps {
		font-size: var(--bx-body-compact-01-font-size, 0.875rem);
		color: var(--bx-text-secondary);
	}
	.device-body > :global(*:not(:last-child)) {
		margin-bottom: var(--bx-spacing-05);
	}
	.metric-label {
		font-size: var(--bx-label-01-font-size, 0.75rem);
		color: var(--bx-text-secondary);
		margin: 0 0 var(--bx-spacing-03);
	}
	.metric-value {
		font-size: var(--bx-body-01-font-size, 0.875rem);
		color: var(--bx-text-primary);
		margin: 0;
	}
</style>
