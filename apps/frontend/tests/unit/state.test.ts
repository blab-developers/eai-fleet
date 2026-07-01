import { describe, it, expect, vi, beforeEach } from 'vitest';
import { listDevices } from '$lib/generated/fleet-backend-api';
import { fleetStore } from '$lib/state.svelte';

// Mock the generated SDK calls so the store is tested without a real backend/fetch.
// getInferenceImage is imported by the store (running-version load); stub it so the
// module resolves even though these tests only exercise loadFleet/filtering.
vi.mock('$lib/generated/fleet-backend-api', () => ({
	listDevices: vi.fn(),
	getInferenceImage: vi.fn().mockResolvedValue({ data: undefined, error: undefined }),
}));
const mockList = vi.mocked(listDevices);

type ListResult = Awaited<ReturnType<typeof listDevices>>;

const deviceA = {
	device_id: 'a',
	name: 'Alpha',
	state: 'running',
	fps: 30,
	gpu_utilization: 50,
	health: 'online',
} as const;

const deviceB = {
	device_id: 'b',
	name: 'Beta',
	state: 'stopped',
	fps: 0,
	gpu_utilization: 0,
	health: 'offline',
} as const;

const deviceC = {
	device_id: 'c',
	name: 'Gamma',
	state: 'running',
	fps: 60,
	gpu_utilization: 90,
	health: 'online',
} as const;

describe('fleetStore.loadFleet', () => {
	beforeEach(() => {
		mockList.mockReset();
		fleetStore.devices = [];
		fleetStore.total = 0;
		fleetStore.online = 0;
		fleetStore.error = null;
		fleetStore.loaded = false;
		fleetStore.lastUpdated = null;
		fleetStore.searchQuery = '';
		fleetStore.healthFilter = 'all';
		fleetStore.sortBy = 'name';
	});

	it('populates devices + derives offline on success, and clears error', async () => {
		mockList.mockResolvedValue({
			data: {
				devices: [deviceA, deviceB],
				total: 2,
				online: 1,
			},
		} as ListResult);

		await fleetStore.loadFleet();

		expect(fleetStore.total).toBe(2);
		expect(fleetStore.online).toBe(1);
		expect(fleetStore.offline).toBe(1);
		expect(fleetStore.devices.map((d) => d.device_id)).toEqual(['a', 'b']);
		expect(fleetStore.error).toBeNull();
		expect(fleetStore.loaded).toBe(true);
		expect(fleetStore.isLoading).toBe(false);
		expect(fleetStore.lastUpdated).toBeInstanceOf(Date);
	});

	it('sets error from a FastAPI detail when the API returns an error (e.g. 502)', async () => {
		mockList.mockResolvedValue({ error: { detail: 'Prometheus query failed: boom' } } as ListResult);

		await fleetStore.loadFleet();

		expect(fleetStore.error).toBe('Prometheus query failed: boom');
		expect(fleetStore.isLoading).toBe(false);
	});

	it('retry() re-runs loadFleet', async () => {
		mockList.mockResolvedValue({
			data: { devices: [deviceA], total: 1, online: 1 },
		} as ListResult);

		await fleetStore.retry();

		expect(fleetStore.total).toBe(1);
		expect(mockList).toHaveBeenCalledTimes(1);
	});
});

describe('fleetStore filtering and sorting', () => {
	beforeEach(() => {
		mockList.mockReset();
		fleetStore.devices = [deviceA, deviceB, deviceC];
		fleetStore.total = 3;
		fleetStore.online = 2;
		fleetStore.searchQuery = '';
		fleetStore.healthFilter = 'all';
		fleetStore.sortBy = 'name';
	});

	it('filters devices by name or device_id', () => {
		fleetStore.searchQuery = 'alp';
		expect(fleetStore.filteredDevices.map((d) => d.device_id)).toEqual(['a']);

		fleetStore.searchQuery = 'c';
		expect(fleetStore.filteredDevices.map((d) => d.device_id)).toEqual(['c']);
	});

	it('filters devices by health', () => {
		fleetStore.healthFilter = 'offline';
		expect(fleetStore.filteredDevices.map((d) => d.device_id)).toEqual(['b']);
	});

	it('sorts devices by health (online first)', () => {
		fleetStore.sortBy = 'health';
		expect(fleetStore.filteredDevices.map((d) => d.device_id)).toEqual(['a', 'c', 'b']);
	});

	it('sorts devices by FPS descending', () => {
		fleetStore.sortBy = 'fps';
		expect(fleetStore.filteredDevices.map((d) => d.device_id)).toEqual(['c', 'a', 'b']);
	});

	it('sorts devices by GPU descending', () => {
		fleetStore.sortBy = 'gpu';
		expect(fleetStore.filteredDevices.map((d) => d.device_id)).toEqual(['c', 'a', 'b']);
	});
});
