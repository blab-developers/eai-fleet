<script lang="ts">
	import { Grid, Row, Column, Tile } from 'carbon-components-svelte';

	interface Props {
		total: number;
		online: number;
		offline: number;
	}

	let { total, online, offline }: Props = $props();
</script>

<Grid class="summary-grid">
	<Row>
		<Column sm={4} md={4} lg={5}>
			<Tile>
				<p class="summary-label">Devices</p>
				<p class="summary-value" data-testid="summary-total">{total}</p>
			</Tile>
		</Column>
		<Column sm={4} md={4} lg={5}>
			<Tile>
				<p class="summary-label">Online</p>
				<p class="summary-value summary-value--online" data-testid="summary-online">{online}</p>
			</Tile>
		</Column>
		<Column sm={4} md={4} lg={5}>
			<Tile>
				<p class="summary-label">Offline</p>
				<p class="summary-value summary-value--offline" data-testid="summary-offline">{offline}</p>
			</Tile>
		</Column>
	</Row>
</Grid>

<style lang="scss">
	.summary-label {
		font-size: var(--bx-label-01-font-size, 0.75rem);
		color: var(--bx-text-secondary);
		margin: 0 0 var(--bx-spacing-03);
	}
	.summary-value {
		font-size: var(--bx-productive-heading-04-font-size, 1.75rem);
		font-weight: 600;
		color: var(--bx-text-primary);
		margin: 0;
	}
	.summary-value--online {
		color: var(--bx-support-success);
	}
	.summary-value--offline {
		color: var(--bx-support-error);
	}
</style>
