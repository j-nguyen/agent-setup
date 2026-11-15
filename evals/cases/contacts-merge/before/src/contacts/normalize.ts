/** Canonical form for comparing and storing emails. */
export function normalizeEmail(email: string): string {
  return email.trim().toLowerCase();
}
