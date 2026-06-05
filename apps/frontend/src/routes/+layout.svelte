<script lang="ts">
  // Load IBM Carbon's g90 (dark) theme as a JS import so Vite bundles it.
  import 'carbon-components-svelte/css/g90.css';
  import Header from 'carbon-components-svelte/src/UIShell/Header.svelte';
  import HeaderUtilities from 'carbon-components-svelte/src/UIShell/HeaderUtilities.svelte';
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
  {@render children()}
</main>

<style>
  main {
    padding: 1.5rem 1rem;
    margin-top: 3rem;
    max-width: 64rem;
  }
  .online,
  .grafana {
    display: inline-flex;
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
