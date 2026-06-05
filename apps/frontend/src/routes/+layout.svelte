<script lang="ts">
  // Load IBM Carbon's g90 (dark) theme as a JS import so Vite bundles it.
  import 'carbon-components-svelte/css/g90.css';
  import { Header, HeaderUtilities, Grid, Row, Column } from 'carbon-components-svelte';
  import { env } from '$env/dynamic/public';
  import { fleetStore } from '$lib/state.svelte';

  let { children } = $props();
  const grafanaUrl = env.EAI_FLEET_FRONTEND_GRAFANA_URL ?? '';
</script>

<Header company="EAI" platformName="Fleet">
  <HeaderUtilities>
    <span class="online">{fleetStore.online}/{fleetStore.total} online</span>
    {#if grafanaUrl}
      <a class="grafana" href={grafanaUrl} target="_blank" rel="noreferrer">Grafana</a>
    {/if}
  </HeaderUtilities>
</Header>

<main>
  <!-- Carbon v11 CSS-Grid layout (Grid/Row/Column) owns the page columns; routes render
       their content inside the single full-width column. No flexbox — see AGENTS conventions. -->
  <Grid>
    <Row>
      <Column>
        {@render children()}
      </Column>
    </Row>
  </Grid>
</main>

<style>
  main {
    /* Horizontal gutters come from the page's Carbon <Grid>; main owns only the
       header offset + vertical rhythm + the centred max-width. */
    padding: 1.5rem 0;
    margin-top: 3rem;
    max-width: 64rem;
  }
  .online,
  .grafana {
    display: inline-grid;
    grid-auto-flow: column;
    align-items: center;
    padding: 0 1rem;
    font-size: 0.875rem;
    color: var(--cds-text-secondary);
  }
  .grafana {
    color: var(--cds-link-primary);
    text-decoration: none;
  }
  .grafana:hover {
    text-decoration: underline;
  }
</style>
