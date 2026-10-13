import { useEffect, useState } from "react";
import { api } from "./api";
export const STORE_KEYS = { signals: "rds.signals.v1", motion: "rds.motion.v1", visualizations: "rds.visualizations.v1" };
export interface Preferences { preview_hz: number; motion_hz: number; stale_after_s: number }
export const DEFAULTS: Preferences = { preview_hz: 2, motion_hz: 10, stale_after_s: 3 };
export function usePreferences() {
  const [value, setValue] = useState(DEFAULTS);
  useEffect(() => { let active = true; api<{ preferences: Preferences }>("/api/settings").then(s => { if (active) setValue(s.preferences); }).catch(() => { /* Defaults keep views usable if preferences cannot be read. */ }); return () => { active = false; }; }, []);
  return value;
}
export function readSaved<T>(key: string, validate: (x: unknown) => x is T, fallback: T): T {
  try { const v: unknown = JSON.parse(localStorage.getItem(key) ?? "null"); return validate(v) ? v : fallback; } catch { return fallback; }
}
export function useSaved<T>(key: string, validate: (x: unknown) => x is T, fallback: T) {
  const [value, setValue] = useState<T>(() => readSaved(key, validate, fallback));
  const [error, setError] = useState("");
  useEffect(() => { try { localStorage.setItem(key, JSON.stringify(value)); setError(""); } catch { setError("Browser storage is unavailable; these changes will not survive a reload."); } }, [key, value]);
  return [value, setValue, error] as const;
}
