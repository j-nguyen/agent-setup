export interface ActivityEvent {
  id: number;
  actor: string;
  action: "login" | "export" | "delete" | "update";
  resource: string;
  at: string; // ISO 8601
}

/** The last 24h of audit events for the org: 20k–50k items. Never modified client-side. */
export async function fetchEvents(): Promise<ActivityEvent[]> {
  const res = await fetch("/api/activity?since=24h");
  if (!res.ok) throw new Error(`activity: ${res.status}`);
  return res.json();
}
