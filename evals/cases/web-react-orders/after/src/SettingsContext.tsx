import { createContext, useContext } from "react";

export interface Settings {
  currency: string;
  compact: boolean;
  setCompact: (v: boolean) => void;
}

export const SettingsContext = createContext<Settings | null>(null);

export function useSettings(): Settings {
  const s = useContext(SettingsContext);
  if (!s) throw new Error("useSettings outside SettingsContext");
  return s;
}
