// Small in-process LRU cache with per-entry TTL. Used for config and feature-flag lookups.

export interface CacheOptions {
  maxEntries: number;
  ttlMs: number;
  now?: () => number;
}

interface Entry<V> {
  value: V;
  expiresAt: number;
}

export class LruCache<V> {
  private readonly entries = new Map<string, Entry<V>>();
  private readonly maxEntries: number;
  private readonly ttlMs: number;
  private readonly now: () => number;

  constructor(opts: CacheOptions) {
    if (opts.maxEntries < 1) throw new Error("maxEntries must be >= 1");
    this.maxEntries = opts.maxEntries;
    this.ttlMs = opts.ttlMs;
    this.now = opts.now ?? Date.now;
  }

  get(key: string): V | undefined {
    const entry = this.entries.get(key);
    if (!entry) return undefined;
    if (entry.expiresAt <= this.now()) {
      this.entries.delete(key);
      return undefined;
    }
    // Re-insert to mark as most recently used.
    this.entries.delete(key);
    this.entries.set(key, entry);
    return entry.value;
  }

  set(key: string, value: V): void {
    this.entries.delete(key);
    this.entries.set(key, { value, expiresAt: this.now() + this.ttlMs });
    while (this.entries.size > this.maxEntries) {
      const oldest = this.entries.keys().next().value as string;
      this.entries.delete(oldest);
    }
  }

  delete(key: string): void {
    this.entries.delete(key);
  }

  get size(): number {
    return this.entries.size;
  }
}
