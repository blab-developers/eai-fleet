# Test Lifecycle & Fixtures in TypeScript (Vitest & Playwright)

This document explains how test lifecycles, fixtures, and setups are structured in the TypeScript/JavaScript ecosystem (Vitest and Playwright), drawing comparisons to Python's `conftest.py` + `tests/common/` pattern used in our backend repositories (`eai_fm`, `eai_catalog`).

---

## The Paradigm Shift: Python vs. TypeScript

In Python's `pytest` framework:
- **`conftest.py`**: Acts as a magic configuration file. It is auto-discovered, handles global hooks, and registers modular fixtures via `pytest_plugins` (making them available globally without explicit imports).
- **Auto-injection**: A test requests a fixture by declaring it as a parameter (e.g. `def test_foo(tmp_path)`).

In TypeScript (Vitest & Playwright):
- **Explicit Imports**: There is no magic auto-discovery of fixture names. If a test needs a fixture, the fixture must be imported.
- **Extended Test runner (`test.extend`)**: We extend the standard test runner to inject custom context. The test files then import this custom `test` object instead of the default runner.

---

## 1. Modular Fixtures: The `test.extend` Pattern

Both Playwright and Vitest support extending the base `test` function to define type-safe, reusable fixtures.

### Playwright Fixture Example (`tests/common/fixtures.ts`)
```typescript
import { test as base } from '@playwright/test';

// 1. Define the type signature of the fixtures
interface MyFixtures {
  mockedDb: { query: () => string[] };
}

// 2. Extend the base test object
export const test = base.extend<MyFixtures>({
  mockedDb: async ({}, use) => {
    // SETUP: runs before the test starts
    const db = { query: () => ['nano-1', 'nano-2'] };
    
    // Provide the fixture to the test
    await use(db);
    
    // TEARDOWN: runs after the test finishes
    console.log('Teardown database connection');
  }
});

export { expect } from '@playwright/test';
```

### Consuming in Test Files (`tests/e2e/fleet.spec.ts`)
```typescript
// Import the custom extended test instead of the default '@playwright/test'
import { test, expect } from '../common/fixtures';

test('lists devices', async ({ mockedDb }) => {
  const devices = mockedDb.query();
  expect(devices).toContain('nano-1');
});
```

---

## 2. Test Lifecycle Management

### Per-Test/Per-Suite Hooks
Standard lifecycle hooks are available in both runners:
- `beforeEach(() => { ... })`: Runs before each test in the file.
- `afterEach(() => { ... })`: Runs after each test in the file.
- `beforeAll(() => { ... })`: Runs once before all tests in the file.
- `afterAll(() => { ... })`: Runs once after all tests in the file.

### Setup Files (`setupFiles` vs. `globalSetup`)

#### 1. Setup Files (Per-File Initialization)
In **Vitest**, `setupFiles` (configured in `vitest.config.ts`) executes a script immediately before running each test file. This is ideal for defining environment globals (like mocking `window.fetch` or local storage) so they are available in every test context.
```typescript
// vitest.config.ts
export default defineConfig({
  test: {
    setupFiles: ['./tests/setup.ts'],
  }
});
```

#### 2. Global Setup & Teardown (Whole Test Run)
For heavy operations that must run once *before the entire test suite starts* and once *after it completes* (e.g., spinning up a mock database server, building frontend assets):
- **Playwright**: Set `globalSetup` and `globalTeardown` paths in `playwright.config.ts`.
- **Vitest**: Set `globalSetup` path in `vitest.config.ts`.

---

## Summary of Equivalent Concepts

| Pytest (Python) | Playwright Test (TS) | Vitest (TS) |
| :--- | :--- | :--- |
| `conftest.py` (fixtures) | `tests/common/fixtures.ts` + `test.extend` | `tests/common/fixtures.ts` + `test.extend` |
| `pytest_plugins` | Explicit `import` of extended `test` | Explicit `import` of extended `test` |
| `pytest_sessionstart` | `globalSetup` (in `playwright.config.ts`) | `globalSetup` (in `vitest.config.ts`) |
| `autouse=True` fixtures | `beforeEach` inside `test.extend` | `beforeEach` inside `test.extend` |
