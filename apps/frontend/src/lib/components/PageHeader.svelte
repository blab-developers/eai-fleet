<script lang="ts">
  // The ONE page header for every route — mirrors eai-nano's $lib/components/PageHeader.svelte
  // (same folder/structure pattern across the two frontends; UX code is NOT shared, just
  // standardized). Sizing + spacing come from Carbon design tokens (`--bx-productive-heading-*`,
  // `--bx-spacing-*`), not hardcoded rem. Pass an `action` snippet for a right-aligned control.
  import type { Snippet } from 'svelte';

  interface Props {
    title: string;
    description?: string;
    testid?: string;
    action?: Snippet;
  }

  let { title, description, testid, action }: Props = $props();
</script>

<div class="page-header">
  <div class="text">
    <h1 class="title" data-testid={testid}>{title}</h1>
    {#if description}
      <p class="desc">{description}</p>
    {/if}
  </div>
  {#if action}
    {@render action()}
  {/if}
</div>

<style>
  .page-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: var(--bx-spacing-05, 1rem);
    border-bottom: 1px solid var(--cds-border-subtle-01);
    padding-bottom: var(--bx-spacing-05, 1rem);
    margin-bottom: var(--bx-spacing-07, 2rem);
  }
  .text {
    display: flex;
    flex-direction: column;
    gap: var(--bx-spacing-03, 0.5rem);
  }
  .title {
    font-size: var(--bx-productive-heading-03-font-size, 1.25rem);
    font-weight: 400;
    color: var(--cds-text-primary);
  }
  .desc {
    font-size: var(--bx-body-long-01-font-size, 0.875rem);
    color: var(--cds-text-secondary);
  }
</style>
