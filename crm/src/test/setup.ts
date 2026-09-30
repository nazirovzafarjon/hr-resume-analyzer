/**
 * Global test setup: fill the gaps between jsdom and a real browser that the
 * app relies on, and start every test from a clean slate.
 */
import { afterEach, vi } from "vitest";
import { cleanup } from "@testing-library/react";

/**
 * Node >= 22 defines its own global `localStorage`/`sessionStorage`, which are
 * unusable unless Node is started with `--localstorage-file`, and they shadow
 * jsdom's working implementation. Install a small spec-compatible in-memory
 * Storage whenever the global one is missing or broken.
 */
class MemoryStorage implements Storage {
  private data = new Map<string, string>();
  get length() {
    return this.data.size;
  }
  clear() {
    this.data.clear();
  }
  getItem(key: string) {
    return this.data.has(key) ? (this.data.get(key) as string) : null;
  }
  key(index: number) {
    return Array.from(this.data.keys())[index] ?? null;
  }
  removeItem(key: string) {
    this.data.delete(key);
  }
  setItem(key: string, value: string) {
    this.data.set(key, String(value));
  }
}

function storageWorks(name: "localStorage" | "sessionStorage"): boolean {
  try {
    const storage = window[name];
    storage.setItem("__probe__", "1");
    storage.removeItem("__probe__");
    return true;
  } catch {
    return false;
  }
}

for (const name of ["localStorage", "sessionStorage"] as const) {
  if (!storageWorks(name)) {
    const storage = new MemoryStorage();
    Object.defineProperty(window, name, { value: storage, configurable: true });
    Object.defineProperty(globalThis, name, { value: storage, configurable: true });
  }
}

// jsdom has no matchMedia (used by the theme provider for "system" theme).
if (!window.matchMedia) {
  window.matchMedia = (query: string) =>
    ({
      matches: false,
      media: query,
      onchange: null,
      addEventListener: () => undefined,
      removeEventListener: () => undefined,
      addListener: () => undefined,
      removeListener: () => undefined,
      dispatchEvent: () => false,
    }) as MediaQueryList;
}

afterEach(() => {
  cleanup();
  localStorage.clear();
  sessionStorage.clear();
  vi.unstubAllGlobals();
});
