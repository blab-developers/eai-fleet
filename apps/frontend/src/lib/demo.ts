/**
 * Demo-mode markers + filter.
 *
 * The backend marks canned devices with `demo: true` when EAI_FLEET_DEMO_MODE is
 * enabled. The operator's per-browser preference decides whether those rows are
 * visible in the frontend.
 */

export const isDemoDevice = (device: { demo?: boolean | null }): boolean => device.demo === true;

export function applyDemoFilter<T>(
  items: T[],
  isDemo: (item: T) => boolean,
  demoMode: boolean,
): T[] {
  return demoMode ? items : items.filter((item) => !isDemo(item));
}
