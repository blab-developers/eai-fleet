/**
 * Fleet state — a Svelte 5 runes store (singleton).
 *
 * The fleet view is a read-through derived server-side from Prometheus (Spec 008), so
 * the store just polls `listDevices()` on an interval and holds the latest snapshot.
 * Components import this singleton and re-derive from it.
 */

import { listDevices, type DeviceView } from '$lib/generated/fleet-backend-api';
import { getErrorMessage } from '$lib/errors';
import { applyDemoFilter, isDemoDevice } from '$lib/demo';
import { preferences } from '$lib/preferences.svelte';
import type { HealthFilter, SortKey } from '$lib/models';

export const POLL_MS = 5000;

class FleetStore {
	devices = $state<DeviceView[]>([]);
	total = $state(0);
	online = $state(0);
	isLoading = $state(false);
	/** Set when a load fails (e.g. 502 — central Prometheus down). */
	error = $state<string | null>(null);
	/** True once the first load attempt has completed (success or failure). */
	loaded = $state(false);
	/** Timestamp of the last successful load. */
	lastUpdated = $state<Date | null>(null);

	/** User-controlled filter/search/sort state. */
	searchQuery = $state('');
	healthFilter = $state<HealthFilter>('all');
	sortBy = $state<SortKey>('name');

	offline = $derived(this.total - this.online);

	/** A search query or health filter is active — distinguishes "filtered to empty" from
	 * "all devices are demo-hidden" so the empty state shows the right message. */
	hasActiveFilter = $derived(this.searchQuery.trim() !== '' || this.healthFilter !== 'all');

	filteredDevices = $derived(this._applyFilterAndSort(this.devices));
	filteredTotal = $derived(this.filteredDevices.length);
	filteredOnline = $derived(this.filteredDevices.filter((d) => d.health === 'online').length);
	filteredOffline = $derived(this.filteredTotal - this.filteredOnline);

	async loadFleet(): Promise<void> {
		this.isLoading = true;
		try {
			const { data, error } = await listDevices();
			if (data) {
				this.devices = data.devices;
				this.total = data.total;
				this.online = data.online;
				this.error = null;
				this.lastUpdated = new Date();
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

	retry(): Promise<void> {
		return this.loadFleet();
	}

	private _applyFilterAndSort(devices: DeviceView[]): DeviceView[] {
		const query = this.searchQuery.trim().toLowerCase();
		// Demo mode (frontend calls the shots): hide backend-marked demo=True devices when the
		// operator's per-browser toggle is off. Reactive on preferences.demoMode.
		let result = applyDemoFilter(devices, isDemoDevice, preferences.demoMode);

		if (query) {
			result = result.filter(
				(d) =>
					d.device_id.toLowerCase().includes(query) ||
					d.name.toLowerCase().includes(query)
			);
		}

		if (this.healthFilter !== 'all') {
			result = result.filter((d) => d.health === this.healthFilter);
		}

		result = [...result].sort((a, b) => {
			switch (this.sortBy) {
				case 'name':
					return a.name.localeCompare(b.name);
				case 'health':
					if (a.health === b.health) return 0;
					return a.health === 'online' ? -1 : 1;
				case 'fps':
					return b.fps - a.fps;
				case 'gpu':
					return b.gpu_utilization - a.gpu_utilization;
				default:
					return 0;
			}
		});

		return result;
	}
}

export const fleetStore = new FleetStore();
