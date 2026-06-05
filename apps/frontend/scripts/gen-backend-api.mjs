#!/usr/bin/env node
/**
 * Generate the typed backend client under src/lib/generated/fleet-backend-api/ from the
 * live FastAPI app, using @hey-api/openapi-ts (config: openapi-ts.config.ts).
 *
 * Two-step pipeline:
 *   1. Boot Python in apps/backend/, call `app.openapi()`, write JSON to a temp file.
 *   2. Run @hey-api/openapi-ts with EAI_OPENAPI_INPUT pointed at that file.
 *
 * Cross-platform: uses Node's spawn (no shell pipes). A temp file avoids Windows
 * stdin-pipe buffer issues that broke large-schema codegen ("Extra data").
 *
 * Run via: `yarn gen:api` from the frontend directory.
 */

import { spawnSync } from 'node:child_process';
import { existsSync, unlinkSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const FRONTEND_ROOT = process.cwd();
const APPS_ROOT = resolve(FRONTEND_ROOT, '..');
const BACKEND_ROOT = resolve(APPS_ROOT, 'backend');

const PY_INLINE =
  'import logging; logging.disable(logging.CRITICAL); ' +
  'import json, sys; from app.main import app; ' +
  'json.dump(app.openapi(), sys.stdout)';

function die(msg, code = 1) {
  console.error(`gen-api: ${msg}`);
  process.exit(code);
}

// 1. Dump the OpenAPI schema from the live FastAPI app. CWD = apps/backend so
// `app.main` resolves. Prefer the backend's OWN venv interpreter — a bare
// `python`/`python3` on PATH usually lacks the backend deps (fastapi).
const venvPy =
  process.platform === 'win32'
    ? resolve(BACKEND_ROOT, '.venv', 'Scripts', 'python.exe')
    : resolve(BACKEND_ROOT, '.venv', 'bin', 'python');
const pyExe = existsSync(venvPy) ? venvPy : process.platform === 'win32' ? 'python' : 'python3';
const py = spawnSync(pyExe, ['-c', PY_INLINE], { cwd: BACKEND_ROOT, encoding: 'utf-8' });
if (py.error) die(`failed to spawn python: ${py.error.message}`);
if (py.status !== 0) die(`python exited ${py.status}\n${py.stderr}`);

// 2. Ensure .svelte-kit/tsconfig.json exists. The project tsconfig.json extends it,
// and openapi-ts reads tsconfig to resolve the `$lib/*` alias used by
// runtimeConfigPath — so without a prior `svelte-kit sync` (fresh CI / clean clone)
// openapi-ts fails with "Couldn't read tsconfig".
const SVELTE_KIT = resolve(FRONTEND_ROOT, 'node_modules', '@sveltejs', 'kit', 'svelte-kit.js');
const sync = spawnSync(process.execPath, [SVELTE_KIT, 'sync'], {
  cwd: FRONTEND_ROOT,
  encoding: 'utf-8',
  stdio: 'inherit',
});
if (sync.status !== 0) die('svelte-kit sync failed', sync.status ?? 1);

// 3. Write schema to a temp file and hand the path to @hey-api/openapi-ts via
// EAI_OPENAPI_INPUT (read by openapi-ts.config.ts).
const tmpFile = join(tmpdir(), `eai-fleet-openapi-${process.pid}.json`);
writeFileSync(tmpFile, py.stdout, 'utf-8');

const CLI = resolve(FRONTEND_ROOT, 'node_modules', '@hey-api', 'openapi-ts', 'bin', 'run.js');
const gen = spawnSync(process.execPath, [CLI], {
  cwd: FRONTEND_ROOT,
  encoding: 'utf-8',
  stdio: 'inherit',
  env: { ...process.env, EAI_OPENAPI_INPUT: tmpFile },
});

// Cleanup temp file regardless of success/failure.
try {
  unlinkSync(tmpFile);
} catch {}

if (gen.error) die(`failed to spawn openapi-ts: ${gen.error.message}`);
if (gen.status !== 0) die(`openapi-ts exited ${gen.status}`, gen.status);

console.log('gen-api: wrote src/lib/generated/fleet-backend-api/');
