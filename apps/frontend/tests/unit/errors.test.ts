import { describe, it, expect } from 'vitest';
import { getErrorMessage } from '$lib/errors';

describe('getErrorMessage', () => {
  it('prefers a FastAPI `detail` field', () => {
    expect(getErrorMessage({ detail: 'central Prometheus down' })).toBe('central Prometheus down');
  });

  it('falls back to `message`', () => {
    expect(getErrorMessage({ message: 'network error' })).toBe('network error');
  });

  it('prefers `detail` over `message` when both are present', () => {
    expect(getErrorMessage({ detail: 'd', message: 'm' })).toBe('d');
  });

  it('stringifies a non-string detail', () => {
    expect(getErrorMessage({ detail: 502 })).toBe('502');
  });

  it('returns the fallback for null / primitives / empty objects', () => {
    expect(getErrorMessage(null)).toBe('Unknown error');
    expect(getErrorMessage('boom')).toBe('Unknown error');
    expect(getErrorMessage({})).toBe('Unknown error');
  });
});
