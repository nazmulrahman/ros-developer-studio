import { useEffect, useState } from "react";
import { api } from "../services/api";
import { DEFAULTS, STORE_KEYS, type Preferences } from "../services/preferences";
import { Notice } from "../components/ui";
import { useDock } from "../services/app";
interface Layout { id: string; name: string; config: Record<string, unknown> }
export function SettingsPage() {
  const [settings, setSettings] = useState<Record<string, unknown> | null>(null);
  const [prefs, setPrefs] = useState<Preferences>(DEFAULTS);
  const [layouts, setLayouts] = useState<Layout[]>([]);
  const [name, setName] = useState(""); const [error, setError] = useState(""); const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  useDock(<p className="muted">Layouts save Signals, Motion and Visualizations configuration. Live samples and access tokens are never included. Server connection settings are read only here.</p>, []);
  async function refresh() { const [s, ls] = await Promise.all([api<Record<string, unknown> & { preferences: Preferences }>("/api/settings"), api<Layout[]>("/api/layouts")]); setSettings(s); setPrefs(s.preferences); setLayouts(ls); }
  useEffect(() => { refresh().catch(e => setError(e.message)); }, []);
  async function run(fn: () => Promise<void>) { setBusy(true); setError(""); setMessage(""); try { await fn(); } catch (e) { setError(e instanceof Error ? e.message : String(e)); } finally { setBusy(false); } }
  async function save() {
    const config = Object.fromEntries(Object.entries(STORE_KEYS).map(([k, key]) => [k, JSON.parse(localStorage.getItem(key) ?? "null")]));
    await api("/api/layouts", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name: name.trim(), config }) });
    setName(""); await refresh(); setMessage("Layout saved.");
  }
  function apply(layout: Layout) {
    for (const [k, key] of Object.entries(STORE_KEYS)) {
      const value = layout.config[k];
      if (value == null) localStorage.removeItem(key); else localStorage.setItem(key, JSON.stringify(value));
    }
    setMessage(`Loaded ${layout.name}. Open a workspace to use it.`);
  }
  return <div className="page"><h1>Settings</h1><p className="sub">Display preferences and saved workspace layouts.</p>
    {error && <Notice kind="err">{error}</Notice>}{message && <Notice>{message}</Notice>}
    <form className="card" onSubmit={e => { e.preventDefault(); void run(async () => { await api("/api/settings", { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(prefs) }); setMessage("Preferences saved. Reopen a workspace to apply them."); }); }}><h2>Sampling and freshness</h2><div className="row2">
      {([['preview_hz', 'Sensor preview Hz', 0.5, 5], ['motion_hz', 'Motion Hz', 1, 50], ['stale_after_s', 'Stale after seconds', 1, 60]] as const).map(([key, label, min, max]) => <label key={key}>{label} <input aria-label={label} type="number" min={min} max={max} step={key === 'preview_hz' ? 0.5 : 1} value={prefs[key]} onChange={e => setPrefs({ ...prefs, [key]: e.target.valueAsNumber })} required /></label>)}
      <button disabled={busy || !settings}>Save preferences</button></div></form>
    <div className="card"><h2>Saved layouts</h2><div className="row2"><input aria-label="Layout name" maxLength={80} placeholder="Layout name" value={name} onChange={e => setName(e.target.value)} /><button disabled={busy || !name.trim()} onClick={() => void run(save)}>Save current layout</button></div>
      {!layouts.length && <p className="muted">No saved layouts.</p>}{layouts.map(l => <div className="row2" key={l.id}><strong>{l.name}</strong><span className="spacer" /><button disabled={busy} onClick={() => void run(async () => apply(l))}>Load</button><button disabled={busy} onClick={() => void run(async () => { await api(`/api/layouts/${l.id}`, { method: "DELETE" }); await refresh(); })}>Delete</button></div>)}</div>
    <div className="card"><h2>Server configuration</h2><p className="muted">Change connection and bag directories in the server configuration file, then restart the backend.</p><div className="kv">{settings && Object.entries(settings).filter(([k]) => k !== "preferences").map(([k, v]) => <div key={k} style={{ display: "contents" }}><span>{k}</span><span className="mono">{JSON.stringify(v)}</span></div>)}</div></div></div>;
}
