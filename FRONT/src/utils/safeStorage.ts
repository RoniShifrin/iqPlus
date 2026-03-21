/**
 * Safe localStorage wrapper — handles SecurityError thrown in private/incognito
 * mode (Safari) and any other storage access failures. Falls back to an in-memory
 * map so the rest of the app continues to work without crashing.
 */

const _mem: Record<string, string> = {};

export const safeStorage = {
  getItem(key: string): string | null {
    try {
      return localStorage.getItem(key);
    } catch {
      return _mem[key] ?? null;
    }
  },

  setItem(key: string, value: string): void {
    try {
      localStorage.setItem(key, value);
    } catch {
      _mem[key] = value;
    }
  },

  removeItem(key: string): void {
    try {
      localStorage.removeItem(key);
    } catch {
      delete _mem[key];
    }
  },
};
