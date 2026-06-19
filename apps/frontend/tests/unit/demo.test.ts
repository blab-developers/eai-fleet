import { describe, expect, it } from 'vitest';
import { applyDemoFilter, isDemoDevice } from '$lib/demo';

describe('demo filtering', () => {
  it('keeps demo rows when demo mode is on', () => {
    const rows = [{ id: 'real' }, { id: 'demo', demo: true }];

    expect(applyDemoFilter(rows, isDemoDevice, true).map((row) => row.id)).toEqual([
      'real',
      'demo',
    ]);
  });

  it('drops marked demo rows when demo mode is off', () => {
    const rows = [{ id: 'real' }, { id: 'demo', demo: true }];

    expect(applyDemoFilter(rows, isDemoDevice, false).map((row) => row.id)).toEqual(['real']);
  });
});
