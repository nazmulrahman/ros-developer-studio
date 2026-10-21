import { useCallback, useEffect, useState } from "react";
import { api } from "../services/api";
import { useApp } from "../services/app";
import { useLive } from "../services/live";
import { Empty, Notice } from "../components/ui";

interface Finding { severity: string; component: string; evidence: string; possible_causes: string[]; suggested_checks: string[]; timestamp_ns?: number | null; topic?: string | null; source_id?: string | null }
interface Profile { id: string; name: string; topic: string; field: string; minimum: number | null; maximum: number | null }
interface LogRow { timestamp_ns: number | null; level: number; name: string; message: string; file: string; function: string; line: number }
interface Correlation { logs: LogRow[]; diagnostics: { timestamp_ns: number; name: string; message: string; level: number }[]; topics: { topic: string; status?: string; evidence?: string }[]; host: { timestamp_ns: number; cpu?: { percent?: number }; memory?: { percent?: number } }[]; events?: { timestamp_ns: number; topic: string; type: string; kind: string; name?: string; message?: string; payload?: unknown }[] }

export function DiagnosticsPage() {
  const { bag, status, seek } = useLive();
  const { setPage, setSelectedTopic } = useApp();
  const offline = status?.mode === "offline" && !!bag;
  const [rows, setRows] = useState<Finding[]>([]);
  const [profiles, setProfiles] = useState<Profile[]>([]);
  const [logs, setLogs] = useState<LogRow[]>([]);
  const [correlated, setCorrelated] = useState<Record<string, Correlation>>({});
  const [error, setError] = useState(""); const [busy, setBusy] = useState(false); const [ran, setRan] = useState(false);
  const [logLevel, setLogLevel] = useState(""); const [logSearch, setLogSearch] = useState("");
  const [form, setForm] = useState({ name: "", topic: "", field: "", minimum: "", maximum: "" });

  const refreshProfiles = useCallback(async () => setProfiles(await api<Profile[]>("/api/diagnostics/profiles")), []);
  const refreshLogs = useCallback(async () => {
    if (!offline) { const params = new URLSearchParams({ limit: "250" }); if (logLevel) params.set("level", logLevel); if (logSearch) params.set("search", logSearch); setLogs((await api<{ rows: LogRow[] }>(`/api/live/logs?${params}`)).rows); }
  }, [offline, logLevel, logSearch]);
  useEffect(() => { void refreshProfiles().catch(e => setError(String(e))); }, [refreshProfiles]);
  useEffect(() => {
    void refreshLogs().catch(e => setError(String(e)));
    if (offline) return;
    const timer = window.setInterval(() => void refreshLogs().catch(e => setError(String(e))), 3000);
    return () => window.clearInterval(timer);
  }, [refreshLogs, offline]);

  async function run() {
    setBusy(true); setError("");
    try { setRows(await api<Finding[]>(offline ? `/api/bags/${bag!.bag_id}/findings` : "/api/diagnostics/findings")); setRan(true); setCorrelated({}); }
    catch (e) { setError(String(e)); } finally { setBusy(false); }
  }
  async function createProfile(e: React.FormEvent) {
    e.preventDefault(); setError("");
    try {
      const body = { name: form.name, topic: form.topic, field: form.field, minimum: form.minimum === "" ? null : Number(form.minimum), maximum: form.maximum === "" ? null : Number(form.maximum) };
      await api("/api/diagnostics/profiles", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
      setForm({ name: "", topic: "", field: "", minimum: "", maximum: "" }); await refreshProfiles();
    } catch (e) { setError(String(e)); }
  }
  async function removeProfile(id: string) {
    try { await api(`/api/diagnostics/profiles/${id}`, { method: "DELETE" }); await refreshProfiles(); }
    catch (e) { setError(String(e)); }
  }
  async function correlate(f: Finding) {
    if (f.timestamp_ns == null) return;
    const key = String(f.timestamp_ns);
    try { const path = offline ? `/api/bags/${bag!.bag_id}/correlate?timestamp_ns=${f.timestamp_ns}&window_s=10` : `/api/diagnostics/correlate?timestamp_ns=${f.timestamp_ns}&window_s=10`; const data = await api<Correlation>(path); setCorrelated(c => ({ ...c, [key]: data })); }
    catch (e) { setError(String(e)); }
  }
  function inspect(f: Finding) {
    if (offline && f.timestamp_ns != null) seek(f.timestamp_ns);
    if (f.topic) { setSelectedTopic(f.topic); setPage("inspector"); }
  }
  function exportReport() {
    const result = { generated_at: new Date().toISOString(), source: offline ? bag?.path : "live", findings: rows, profiles, live_ros_logs: offline ? [] : logs, correlated_evidence: correlated };
    const url = URL.createObjectURL(new Blob([JSON.stringify(result, null, 2)], { type: "application/json" }));
    const a = document.createElement("a"); a.href = url; a.download = "studio-diagnostic-report.json"; a.click(); URL.revokeObjectURL(url);
  }

  return <div className="page">
    <h1>Diagnostics</h1>
    <p className="sub">Evidence from ROS logs, topic timing, TF, recorded samples and your configured expectations.</p>
    <div className="row2"><button onClick={() => void run()} disabled={busy}>{busy ? "Analysing…" : "Run checks"}</button>
      <button onClick={exportReport} disabled={!ran}>Export evidence report</button>
      <span>{offline ? bag!.path : "Live source · ROS logs retained up to 5,000 entries"}</span></div>
    {error && <Notice kind="err">{error}</Notice>}

    <h2>Expectation profiles</h2>
    <p className="muted">Set robot-specific numeric bounds. Live checks use the latest observed message; bag checks scan up to 10,000 recorded messages per topic.</p>
    <form className="row2" onSubmit={e => void createProfile(e)}>
      <input required maxLength={80} placeholder="Expectation name" aria-label="Expectation name" value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} />
      <input required placeholder="/topic" aria-label="Topic" value={form.topic} onChange={e => setForm({ ...form, topic: e.target.value })} />
      <input required placeholder="field.path" aria-label="Numeric field path" value={form.field} onChange={e => setForm({ ...form, field: e.target.value })} />
      <input type="number" step="any" placeholder="Minimum" aria-label="Minimum expected value" value={form.minimum} onChange={e => setForm({ ...form, minimum: e.target.value })} />
      <input type="number" step="any" placeholder="Maximum" aria-label="Maximum expected value" value={form.maximum} onChange={e => setForm({ ...form, maximum: e.target.value })} />
      <button type="submit">Save expectation</button>
    </form>
    <div className="bag-findings">{profiles.map(p => <div className="finding info" key={p.id}><strong>{p.name}</strong> · <span className="mono">{p.topic}.{p.field}</span> · {p.minimum ?? "−∞"}…{p.maximum ?? "∞"}<button style={{ float: "right" }} onClick={() => void removeProfile(p.id)}>Remove</button></div>)}</div>

    {!offline && <><div className="row2"><h2>ROS log buffer</h2><select aria-label="ROS log severity" value={logLevel} onChange={e => setLogLevel(e.target.value)}><option value="">All levels</option><option value="10">Debug</option><option value="20">Info</option><option value="30">Warn</option><option value="40">Error</option><option value="50">Fatal</option></select><input aria-label="Search ROS logs" placeholder="Search logs" value={logSearch} onChange={e => setLogSearch(e.target.value)} /><button onClick={() => void refreshLogs()}>Refresh logs</button></div>
      <p className="muted">Captures `/rosout` while the agent is connected. The in-memory ring retains the newest 5,000 entries.</p>
      <div className="bag-findings">{logs.slice(-30).reverse().map((l, i) => <details className={`finding ${l.level >= 40 ? "error" : l.level >= 30 ? "warning" : "info"}`} key={`${l.timestamp_ns}:${i}`}>
        <summary><strong>{l.level >= 50 ? "FATAL" : l.level >= 40 ? "ERROR" : l.level >= 30 ? "WARN" : l.level >= 20 ? "INFO" : "DEBUG"}</strong> · {l.name} · {l.message}</summary>
        <p className="mono">{l.file}:{l.line} · {l.function} · {l.timestamp_ns ?? "time unavailable"}</p>
      </details>)}</div>{!logs.length && <Notice>No `/rosout` messages captured yet. Capture starts when this topic is present in the live ROS graph.</Notice>}</>}

    <h2>Findings</h2>
    {ran && !rows.length && <Notice>No faults detected by the available checks. Unmonitored components and unsampled intervals remain unknown.</Notice>}
    {!ran && <Empty title="Run diagnostic checks">Findings separate measured evidence from possible causes. Live checks use current observations; bag checks use recorded timing and bounded samples.</Empty>}
    <div className="bag-findings">{rows.map((f, i) => { const key = String(f.timestamp_ns ?? i); const related = correlated[key]; return <details className={`finding ${f.severity}`} key={`${f.component}:${i}`} open>
      <summary><strong>{f.severity.toUpperCase()}</strong> · {f.component}</summary><p>{f.evidence}</p>
      <b>Possible causes</b><ul>{f.possible_causes.map(x => <li key={x}>{x}</li>)}</ul>
      <b>Suggested checks</b><ul>{f.suggested_checks.map(x => <li key={x}>{x}</li>)}</ul>
      <div className="row2">{f.topic && <button onClick={() => inspect(f)}>Inspect {f.topic}{offline && f.timestamp_ns != null ? " at incident time" : ""}</button>}
        {f.timestamp_ns != null && <button onClick={() => void correlate(f)}>Correlate ±10 seconds</button>}
        {f.timestamp_ns != null && <span className="muted">Timestamp {f.timestamp_ns}</span>}</div>
      {related && <div><h3>Nearby evidence</h3>{related.events?.map((e, n) => <p key={`e${n}`}>{e.kind} · {e.topic} · {e.name ?? e.type}: {e.message ?? JSON.stringify(e.payload ?? {})}</p>)}{related.logs.map((l, n) => <p key={`l${n}`}>Log · {l.name}: {l.message}</p>)}{related.diagnostics.map((d, n) => <p key={`d${n}`}>Diagnostic · {d.name}: {d.message}</p>)}{related.topics.map((t, n) => <p key={`t${n}`}>Topic · {t.topic}: {t.status} {t.evidence}</p>)}{related.host.map((h, n) => <p key={`h${n}`}>Host sample · CPU {h.cpu?.percent ?? "—"}% · memory {h.memory?.percent ?? "—"}%</p>)}{!(related.events?.length) && !related.logs.length && !related.diagnostics.length && !related.topics.length && !related.host.length && <p className="muted">No retained events fell inside this time window.</p>}</div>}
    </details>; })}</div>
  </div>;
}
