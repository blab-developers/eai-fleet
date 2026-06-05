/**
 * Fleet state — a Svelte 5 runes store (singleton).
 *
 * The fleet view is a read-through derived server-side from Prometheus (Spec 008), so
 * the store just polls `listDevices()` on an interval and holds the latest snapshot.
 * Components import this singleton and re-derive from it.
 */

import { listDevices, type DeviceView } from '$lib/generated/fleet-backend-api';
import { getErrorMessage } from '$lib/errors';

class FleetStore {
  devices = $state<DeviceView[]>([]);
  total = $state(0);
  online = $state(0);
  isLoading = $state(false);
  /** Set when a load fails (e.g. 502 — central Prometheus down). */
  error = $state<string | null>(null);
  /** True once the first load attempt has completed (success or failure). */
  loaded = $state(false);

  offline = $derived(this.total - this.online);

  async loadFleet(): Promise<void> {
    this.isLoading = true;
    try {
      const { data, error } = await listDevices();
      if (data) {
        this.devices = data.devices;
        this.total = data.total;
        this.online = data.online;
        this.error = null;
      } else {
        this.error = getErrorMessage(error);
      }
    } catch (e) {
      this.error = getErrorMessage(e);
    } finally {
      this.isLoading = false;
      this.loaded = true;
    }
  }
}

export const fleetStore = new FleetStore();
