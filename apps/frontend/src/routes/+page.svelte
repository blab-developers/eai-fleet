<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import Accordion from 'carbon-components-svelte/src/Accordion/Accordion.svelte';
  import AccordionItem from 'carbon-components-svelte/src/Accordion/AccordionItem.svelte';
  import Tag from 'carbon-components-svelte/src/Tag/Tag.svelte';
  import Button from 'carbon-components-svelte/src/Button/Button.svelte';
  import TextInput from 'carbon-components-svelte/src/TextInput/TextInput.svelte';
  import InlineNotification from 'carbon-components-svelte/src/Notification/InlineNotification.svelte';
  import Loading from 'carbon-components-svelte/src/Loading/Loading.svelte';
  import ChartLine from 'carbon-icons-svelte/lib/ChartLine.svelte';
  import { env } from '$env/dynamic/public';
  import { fleetStore } from '$lib/state.svelte';
  import { getErrorMessage } from '$lib/errors';
  import { setInferenceImage, type DeviceView } from '$lib/generated/fleet-backend-api';

  const POLL_MS = 5000;
  const grafanaBase = env.EAI_FLEET_FRONTEND_GRAFANA_URL ?? '';

  // Per-device set-image control state, keyed by device_id.
  let imageInput = $state<Record<string, string>>({});
  let setBusy = $state<Record<string, boolean>>({});
  let setNote = $state<Record<string, string | null>>({});
  let setError = $state<Record<string, string | null>>({});

  let timer: ReturnType<typeof setInterval> | undefined;

  onMount(() => {
    fleetStore.loadFleet();
    timer = setInterval(() => fleetStore.loadFleet(), POLL_MS);
  });
  onDestroy(() => {
    if (timer) clearInterval(timer);
  });

  function grafanaLink(deviceId: string): string {
    if (!grafanaBase) return '';
    const sep = grafanaBase.includes('?') ? '&' : '?';
    return `${grafanaBase}${sep}var-device=${encodeURIComponent(deviceId)}`;
  }

  async function handleSetImage(deviceId: string): Promise<void> {
    const image = (imageInput[deviceId] ?? '').trim();
    if (!image) return;
    setBusy[deviceId] = true;
    setNote[deviceId] = null;
    setError[deviceId] = null;
    try {
      const { data, error } = await setInferenceImage({
        path: { device_id: deviceId },
        body: { image },
      });
      if (data) {
        setNote[deviceId] = `${data.scope}: ${data.note}`;
        imageInput[deviceId] = '';
      } else {
        setError[deviceId] = getErrorMessage(error);
      }
    } catch (e) {
      setError[deviceId] = getErrorMessage(e);
    } finally {
      setBusy[deviceId] = false;
    }
  }
</script>

<h1>Fleet</h1>

<div class="summary">
  <div class="metric">
    <span class="label">Devices</span>
    <span class="value" data-testid="summary-total">{fleetStore.total}</span>
  </div>
  <div class="metric">
    <span class="label">Online</span>
    <span class="value online" data-testid="summary-online">{fleetStore.online}</span>
  </div>
  <div class="metric">
    <span class="label">Offline</span>
    <span class="value offline" data-testid="summary-offline">{fleetStore.offline}</span>
  </div>
  {#if fleetStore.isLoading}<Loading withOverlay={false} small />{/if}
</div>

{#if fleetStore.error}
  <InlineNotification
    kind="error"
    title="Fleet view unavailable"
    subtitle={fleetStore.error}
    hideCloseButton
  />
{/if}

{#if !fleetStore.loaded}
  <Loading withOverlay={false} />
{:else if fleetStore.devices.length === 0 && !fleetStore.error}
  <p class="empty">No devices in the fleet yet.</p>
{:else}
  <Accordion>
    {#each fleetStore.devices as device (device.device_id)}
      {@const online = device.health === 'online'}
      <AccordionItem>
        <span slot="title" class="row-title" data-testid="device-title-{device.device_id}">
          <span class="name">{device.name}</span>
          <Tag type={online ? 'green' : 'red'} size="sm">{device.health}</Tag>
          <span class="fps">{device.fps.toFixed(1)} fps</span>
        </span>

        <div class="body" data-testid="device-body-{device.device_id}">
          <dl class="metrics">
            <div><dt>State</dt><dd data-testid="metric-state">{device.state}</dd></div>
            <div><dt>FPS</dt><dd data-testid="metric-fps">{device.fps.toFixed(1)}</dd></div>
            <div><dt>GPU</dt><dd data-testid="metric-gpu">{device.gpu_utilization.toFixed(0)}%</dd></div>
            <div><dt>Health</dt><dd data-testid="metric-health">{device.health}</dd></div>
          </dl>

          {#if grafanaBase}
            <Button
              kind="ghost"
              size="sm"
              icon={ChartLine}
              href={grafanaLink(device.device_id)}
              target="_blank"
            >
              History (Grafana)
            </Button>
          {/if}

          <div class="set-image">
            <TextInput
              size="sm"
              labelText="Set inference image"
              placeholder="registry.endoscopeai.com/eai-nano/inference:vX.Y.Z"
              bind:value={imageInput[device.device_id]}
            />
            <Button
              size="sm"
              disabled={setBusy[device.device_id] || !(imageInput[device.device_id] ?? '').trim()}
              onclick={() => handleSetImage(device.device_id)}
            >
              Apply
            </Button>
          </div>

          {#if setNote[device.device_id]}
            <InlineNotification kind="success" title="Image set" subtitle={setNote[device.device_id] ?? ''} lowContrast />
          {/if}
          {#if setError[device.device_id]}
            <InlineNotification kind="error" title="Set image failed" subtitle={setError[device.device_id] ?? ''} lowContrast />
          {/if}
        </div>
      </AccordionItem>
    {/each}
  </Accordion>
{/if}

<style>
  h1 {
    font-size: 1.5rem;
    font-weight: 400;
    margin-bottom: 1rem;
  }
  .summary {
    display: flex;
    gap: 2rem;
    align-items: center;
    background-color: var(--cds-layer-01);
    border: 1px solid var(--cds-border-subtle-01);
    padding: 0.75rem 1rem;
    margin-bottom: 1rem;
  }
  .metric {
    display: flex;
    flex-direction: column;
  }
  .metric .label {
    font-size: 0.75rem;
    color: var(--cds-text-secondary);
  }
  .metric .value {
    font-size: 1.5rem;
    font-weight: 600;
    color: var(--cds-text-primary);
  }
  .value.online {
    color: var(--cds-support-success);
  }
  .value.offline {
    color: var(--cds-support-error);
  }
  .row-title {
    display: inline-flex;
    align-items: center;
    gap: 0.75rem;
  }
  .row-title .name {
    font-weight: 500;
  }
  .row-title .fps {
    font-size: 0.8125rem;
    color: var(--cds-text-secondary);
  }
  .metrics {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(8rem, 1fr));
    gap: 0.5rem 1.5rem;
    margin: 0 0 0.75rem;
  }
  .metrics dt {
    font-size: 0.75rem;
    color: var(--cds-text-secondary);
  }
  .metrics dd {
    margin: 0;
    font-size: 0.9375rem;
    color: var(--cds-text-primary);
  }
  .set-image {
    display: flex;
    align-items: flex-end;
    gap: 0.5rem;
    margin-top: 0.5rem;
  }
  .set-image :global(.bx--form-item) {
    flex: 1;
  }
  .empty {
    color: var(--cds-text-secondary);
    padding: 2rem 0;
  }
</style>
