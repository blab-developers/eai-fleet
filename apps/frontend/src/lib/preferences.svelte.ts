/**
 * Frontend preferences: per-browser UI choices persisted in localStorage.
 */

import { browser } from '$app/environment';
import type { StoredPrefs } from '$lib/models';

export const PREFS_KEY = 'eai-fleet-prefs';

function load(): StoredPrefs {
  const empty: StoredPrefs = { demoMode: true };
  if (!browser) return empty;
  try {
    const raw = localStorage.getItem(PREFS_KEY);
    return raw ? { ...empty, ...JSON.parse(raw) } : empty;
  } catch {
    return empty;
  }
}

class Preferences {
  #prefs = load();
  #demoMode = $state<boolean>(this.#prefs.demoMode);

  get demoMode(): boolean {
    return this.#demoMode;
  }

  set demoMode(value: boolean) {
    this.#demoMode = value;
    this.#save();
  }

  clear(): void {
    this.#demoMode = true;
    if (!browser) return;
    try {
      localStorage.removeItem(PREFS_KEY);
    } catch {
      /* localStorage blocked; preference reset still applies in memory */
    }
  }

  #save(): void {
    if (!browser) return;
    try {
      localStorage.setItem(PREFS_KEY, JSON.stringify({ demoMode: this.#demoMode }));
    } catch {
      /* localStorage blocked; preferences are best-effort */
    }
  }
}

export const preferences = new Preferences();
