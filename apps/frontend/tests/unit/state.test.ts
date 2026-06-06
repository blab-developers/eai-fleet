import { describe, it, expect, vi, beforeEach } from 'vitest';
import { listDevices } from '$lib/generated/fleet-backend-api';
import { fleetStore } from '$lib/state.svelte';

// Mock the generated SDK call so the store is tested without a real backend/fetch.
vi.mock('$lib/generated/fleet-backend-api', () => ({ listDevices: vi.fn() }));
const mockList = vi.mocked(listDevices);

type ListResult = Awaited<ReturnType<typeof listDevices>>;

describe('fleetStore.loadFleet', () => {
  beforeEach(() => mockList.mockReset());

  it('populates devices + derives offline on success, and clears error', async () => {
    mockList.mockResolvedValue({
      data: {
        devices: [
          { device_id: 'a', name: 'a', state: 'running', fps: 30, gpu_utilization: 50, health: 'online' },
          { device_id: 'b', name: 'b', state: 'stopped', fps: 0, gpu_utilization: 0, health: 'offline' },
        ],
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
  });

  it('sets error from a FastAPI detail when the API returns an error (e.g. 502)', async () => {
    mockList.mockResolvedValue({ error: { detail: 'Prometheus query failed: boom' } } as ListResult);

    await fleetStore.loadFleet();

    expect(fleetStore.error).toBe('Prometheus query failed: boom');
    expect(fleetStore.isLoading).toBe(false);
  });
});
