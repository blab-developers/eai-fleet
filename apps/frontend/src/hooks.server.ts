import type { Handle } from '@sveltejs/kit';
import { env } from '$env/dynamic/private';

/** Proxy /api/* to the backend container.
 *
 *  The frontend ships as its own adapter-node container; the browser always calls
 *  same-origin /api/* (see $lib/hey-api.ts baseUrl ''), and this hook forwards to the
 *  backend. EAI_FLEET_BACKEND_URL is set by the eai-infra role (prod) / .env (dev) —
 *  e.g. http://<server_ip>:8088. Validated lazily on the first /api/* request so
 *  `yarn dev` for pure UI work doesn't require it. */
const BACKEND = env.EAI_FLEET_BACKEND_URL;

export const handle: Handle = async ({ event, resolve }) => {
  if (event.url.pathname.startsWith('/api/')) {
    if (!BACKEND) {
      return new Response(
        JSON.stringify({ detail: 'Missing env EAI_FLEET_BACKEND_URL (set in .env or by the eai-infra role).' }),
        { status: 502, headers: { 'Content-Type': 'application/json' } },
      );
    }

    const targetUrl = `${BACKEND}${event.url.pathname}${event.url.search}`;
    const headers: Record<string, string> = {};
    event.request.headers.forEach((value, key) => {
      if (key !== 'host' && key !== 'connection') headers[key] = value;
    });

    // `duplex` is required by undici when streaming a request body but isn't yet in
    // the lib.dom RequestInit type — widen it locally instead of suppressing.
    const init: RequestInit & { duplex?: 'half' } = {
      method: event.request.method,
      headers,
      body: event.request.body,
      duplex: 'half',
    };
    const response = await fetch(targetUrl, init);

    return new Response(response.body, {
      status: response.status,
      statusText: response.statusText,
      headers: response.headers,
    });
  }

  return resolve(event);
};
