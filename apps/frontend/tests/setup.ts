import { vi } from 'vitest';

// The generated API client calls fetch at import time; a default stub keeps module imports
// side-effect-free — individual tests override it with vi.mocked(fetch).
global.fetch = vi.fn();
