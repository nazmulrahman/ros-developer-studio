export const dash = "—";
export const fmtNum = (v: number | null | undefined, d = 2) => (v == null || !isFinite(v) ? dash : v.toFixed(d));
export const fmtHz = (v: number | null | undefined) => (v == null ? dash : v >= 100 ? v.toFixed(0) : v >= 10 ? v.toFixed(1) : v.toFixed(2));
export function fmtBytes(n: number | null | undefined): string {
  if (n == null) return dash;
  const u = ["B", "KiB", "MiB", "GiB", "TiB"]; let i = 0; let v = n;
  while (v >= 1024 && i < u.length - 1) { v /= 1024; i++; }
  return `${v.toFixed(i ? 1 : 0)} ${u[i]}`;
}
export function fmtBps(b: number | null | undefined): string {
  if (b == null) return dash;
  return b >= 1e6 ? `${(b / 1e6).toFixed(2)} Mbit/s` : b >= 1e3 ? `${(b / 1e3).toFixed(1)} kbit/s` : `${b.toFixed(0)} bit/s`;
}
export function fmtDur(s: number | null | undefined): string {
  if (s == null) return dash;
  const d = Math.floor(s / 86400), h = Math.floor((s % 86400) / 3600), m = Math.floor((s % 3600) / 60);
  return d ? `${d}d ${h}h ${m}m` : h ? `${h}h ${m}m` : m ? `${m}m ${Math.floor(s % 60)}s` : `${s.toFixed(1)}s`;
}
export function fmtClock(ns: number | null | undefined): string {
  if (ns == null) return dash;
  const d = new Date(ns / 1e6);
  return d.toLocaleTimeString([], { hour12: false }) + "." + String(d.getMilliseconds()).padStart(3, "0");
}
