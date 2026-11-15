import type { Contact } from "./types";

export function mergeContacts(contacts: Contact[]): Contact[] {
  const result: Contact[] = [];
  for (const c of contacts) {
    const existing = result.find((r) => r.email === c.email.trim());
    if (existing) {
      existing.tags = existing.tags.concat(c.tags.filter((t) => !existing.tags.includes(t)));
      if (c.createdAt < existing.createdAt) {
        existing.createdAt = c.createdAt;
      }
    } else {
      c.email = c.email.trim();
      result.push(c);
    }
  }
  return result;
}
