/**
 * Frontend-local types and constants that are not generated from the backend
 * OpenAPI spec.
 */

export type HealthFilter = 'all' | 'online' | 'offline';
export type SortKey = 'name' | 'health' | 'fps' | 'gpu';

export const HEALTH_FILTER_OPTIONS: { value: HealthFilter; label: string }[] = [
	{ value: 'all', label: 'All devices' },
	{ value: 'online', label: 'Online' },
	{ value: 'offline', label: 'Offline' },
];

export const SORT_OPTIONS: { value: SortKey; label: string }[] = [
	{ value: 'name', label: 'Name' },
	{ value: 'health', label: 'Health (online first)' },
	{ value: 'fps', label: 'FPS (high to low)' },
	{ value: 'gpu', label: 'GPU % (high to low)' },
];

/** Best-effort regex for a container image reference. Allows host:port. */
export const IMAGE_TAG_PATTERN = /^(?:[a-zA-Z0-9](?:[a-zA-Z0-9._-]*[a-zA-Z0-9])?(?::\d+)?\/)?(?:[a-zA-Z0-9._-]+\/)*[a-zA-Z0-9._-]+(?::[a-zA-Z0-9._-]+)?$/;

export function isValidImageTag(value: string): boolean {
	return IMAGE_TAG_PATTERN.test(value.trim());
}

/**
 * Per-browser UI preferences persisted to localStorage. This is NOT config (deploy-time env)
 * and NOT device state (server-owned); it only remembers what THIS browser last chose.
 */
export interface StoredPrefs {
	demoMode: boolean;
}
