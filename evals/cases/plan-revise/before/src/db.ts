// Minimal table store. In production the same interface is backed by Postgres
// (see infra repo); in dev and tests it's in memory.

export type Row = { id: string } & Record<string, unknown>;

export class Table<T extends Row> {
  private rows = new Map<string, T>();

  insert(row: T): T {
    if (this.rows.has(row.id)) throw new Error(`duplicate id ${row.id}`);
    this.rows.set(row.id, structuredClone(row));
    return structuredClone(row);
  }

  get(id: string): T | undefined {
    const r = this.rows.get(id);
    return r ? structuredClone(r) : undefined;
  }

  update(id: string, patch: Partial<T>): T {
    const r = this.rows.get(id);
    if (!r) throw new Error(`no row ${id}`);
    const next = { ...r, ...patch, id } as T;
    this.rows.set(id, next);
    return structuredClone(next);
  }

  where(pred: (r: T) => boolean): T[] {
    return [...this.rows.values()].filter(pred).map((r) => structuredClone(r));
  }

  delete(id: string): boolean {
    return this.rows.delete(id);
  }

  clear(): void {
    this.rows.clear();
  }
}

let counter = 0;
export function newId(prefix: string): string {
  counter += 1;
  return `${prefix}_${Date.now().toString(36)}${counter.toString(36)}`;
}
