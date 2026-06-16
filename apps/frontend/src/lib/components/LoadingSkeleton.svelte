<script lang="ts">
	import { Tile, SkeletonPlaceholder, SkeletonText } from 'carbon-components-svelte';
</script>

<div data-testid="fleet-loading">
	<Tile>
		<SkeletonPlaceholder />
		<SkeletonText paragraph lines={6} />
	</Tile>
</div>
