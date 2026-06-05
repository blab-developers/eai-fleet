import { defineConfig } from '@hey-api/openapi-ts';

// The schema is dumped from the live FastAPI app by scripts/gen-backend-api.mjs, which
// writes it to a temp file and sets EAI_OPENAPI_INPUT. We never commit the raw schema;
// the generated client under src/lib/generated/fleet-backend-api IS the artifact.
const input = process.env.EAI_OPENAPI_INPUT;
if (!input) {
  throw new Error(
    'EAI_OPENAPI_INPUT is not set — run `yarn gen:api` (scripts/gen-backend-api.mjs) instead of invoking openapi-ts directly.',
  );
}

export default defineConfig({
  input,
  output: 'src/lib/generated/fleet-backend-api',
  plugins: [
    {
      name: '@hey-api/client-fetch',
      // Configure the generated client at creation time (baseUrl) so no hand-written
      // wrapper is needed — see src/lib/hey-api.ts.
      runtimeConfigPath: '$lib/hey-api',
    },
  ],
});
