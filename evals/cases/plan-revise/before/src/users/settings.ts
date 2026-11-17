// Per-user settings. One row per user, created lazily with defaults.
import { Table } from "../db.ts";

export type Theme = "light" | "dark" | "system";

export type NotificationPrefs = {
  // In-app notification kinds the user has muted (see notifications/types.ts).
  mutedKinds: string[];
};

export type UserSettings = {
  id: string; // same as the user id
  theme: Theme;
  locale: string;
  // IANA time zone, e.g. "Europe/Berlin". Set from the browser on first login.
  timezone: string;
  notifications: NotificationPrefs;
  updatedAt: string;
};

export const DEFAULT_SETTINGS: Omit<UserSettings, "id" | "updatedAt"> = {
  theme: "system",
  locale: "en",
  timezone: "UTC",
  notifications: { mutedKinds: [] },
};

export const settingsTable = new Table<UserSettings>();

export function getSettings(userId: string): UserSettings {
  const existing = settingsTable.get(userId);
  if (existing) return existing;
  return settingsTable.insert({
    id: userId,
    ...structuredClone(DEFAULT_SETTINGS),
    updatedAt: new Date().toISOString(),
  });
}

export function validateTimezone(tz: string): boolean {
  try {
    new Intl.DateTimeFormat("en", { timeZone: tz });
    return true;
  } catch {
    return false;
  }
}

export type SettingsPatch = Partial<Omit<UserSettings, "id" | "updatedAt">>;

export function updateSettings(userId: string, patch: SettingsPatch): UserSettings {
  getSettings(userId);
  if (patch.timezone !== undefined && !validateTimezone(patch.timezone)) {
    throw new Error(`invalid timezone: ${patch.timezone}`);
  }
  if (patch.theme !== undefined && !["light", "dark", "system"].includes(patch.theme)) {
    throw new Error(`invalid theme: ${patch.theme}`);
  }
  return settingsTable.update(userId, { ...patch, updatedAt: new Date().toISOString() });
}
