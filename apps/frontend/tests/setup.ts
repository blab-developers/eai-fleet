import { vi } from 'vitest';

// jsdom has no fetch; the generated API client uses it. A default stub keeps module
// imports side-effect-free — individual tests override it with vi.mocked(fetch).
global.fetch = vi.fn();
