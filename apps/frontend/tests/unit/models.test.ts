import { describe, it, expect } from 'vitest';
import { isValidImageTag } from '$lib/models';

describe('isValidImageTag', () => {
	it('accepts common container image references', () => {
		expect(isValidImageTag('registry.endoscopeai.com/eai-nano/inference:v1.2.3')).toBe(true);
		expect(isValidImageTag('eai-nano/inference:latest')).toBe(true);
		expect(isValidImageTag('inference:1.0')).toBe(true);
		expect(isValidImageTag('my-registry:5000/repo/image:tag')).toBe(true);
	});

	it('rejects empty or malformed strings', () => {
		expect(isValidImageTag('')).toBe(false);
		expect(isValidImageTag('   ')).toBe(false);
		expect(isValidImageTag('image with spaces:tag')).toBe(false);
		expect(isValidImageTag(':tagonly')).toBe(false);
	});
});
