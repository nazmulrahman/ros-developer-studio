import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import uPlot from "uplot";
import { Gate } from "../components/Gate";
import { Empty, Notice } from "../components/ui";
import { Plot } from "../plots/Plot";
import { api } from "../services/api";
import { useApp, useDock } from "../services/app";
import { fmtNum } from "../services/format";
import { useChannel, useLive } from "../services/live";
import type { FieldInfo, SampleEvent, TopicDetail } from "../types/api";

interface SeriesCfg { id: string; topic: string; path: string; type: string; label: string; color: string }
interface Buf { t: number[]; v: number[] }
interface Stat { latest: number | null; min: number | null; max: number | null; avg: number | null; n: number }
const COLORS = ["#49B6E8", "#34C995", "#F5AD57", "#EF6464", "#B58CFF", "#E6D36F", "#7FD1B9", "#FF8FB1"];
const WINDOWS = [10, 30, 60, 300, 600];
const RATES = [1, 2, 5, 10, 20, 50];
const KEEP_S = 600, MAX_PTS = 12000;
const STORE = "rds.signals.v1";

const lower = (a: number[], x: number) => { let lo = 0, hi = a.length; while (lo < hi) { const m = (lo + hi) >> 1; if (a[m] < x) lo = m + 1; else hi = m; } return lo; };
const upper = (a: number[], x: number) => { let lo = 0, hi = a.length; while (lo < hi) { const m = (lo + hi) >> 1; if (a[m] <= x) lo = m + 1; else hi = m; } return lo; };

function load() { try { return JSON.parse(localStorage.getItem(STORE) ?? "null"); } catch { return null; } }

export function SignalsPage() {
  const { watch, unwatch, graph, status } = useLive();
  const { selectedTopic } = useApp();
  const saved = useRef(load()).current;
  const [series, setSeries] = useState<SeriesCfg[]>(saved?.series ?? []);
  const [windowS, setWindowS] = useState<number>(saved?.windowS ?? 30);
  const [rate, setRate] = useState<number>(saved?.rate ?? 10);
  const [paused, setPaused] = useState(false);
  const [view, setView] = useState<{ min: number; max: number } | null>(null);
  const [topic, setTopic] = useState(selectedTopic ?? "");
  const [detail, setDetail] = useState<TopicDetail | null>(null);
  const [detailErr, setDetailErr] = useState<string | null>(null);
  const [filter, setFilter] = useState("");
  const [idx, setIdx] = useState<{ path: string; value: string } | null>(null);
  const [selId, setSelId] = useState<string | null>(null);
  const [frame, setFrame] = useState<{ data: uPlot.AlignedData; xRange: [number, number] | null; stats: Record<string, Stat> }>({ data: [[]], xRange: null, stats: {} });
  const [watchErrs, setWatchErrs] = useState<string[]>([]);

  const bufs = useRef(new Map<string, Buf>());
  const seriesRef = useRef(series); seriesRef.current = series;
  const watched = useRef(new Set<string>());

  useEffect(() => { localStorage.setItem(STORE, JSON.stringify({ series, windowS, rate })); }, [series, windowS, rate]);

  // topic schema for the field picker
  useEffect(() => {
    setDetail(null); setDetailErr(null);
    if (!topic) return;
    const h = setTimeout(() => api<TopicDetail>(`/api/live/topic?name=${encodeURIComponent(topic)}`).then(setDetail).catch(e => setDetailErr(String(e.message ?? e))), 250);
    return () => clearTimeout(h);
  }, [topic, graph.updated]);

  // subscribe only to topics that have series on this page; release on change/unmount
  useEffect(() => {
    const byTopic = new Map<string, string[]>();
    series.forEach(s => byTopic.set(s.topic, [...(byTopic.get(s.topic) ?? []), s.path]));
    byTopic.forEach((fields, t) => { watch(t, { hz: rate, fields }); watched.current.add(t); });
    watched.current.forEach(t => { if (!byTopic.has(t)) { unwatch(t); watched.current.delete(t); } });
  }, [series, rate, watch, unwatch, status?.agent.state]);
  useEffect(() => () => { watched.current.forEach(t => unwatch(t)); watched.current.clear(); }, [unwatch]);
  useChannel("watch_error", (e: { topic: string; message: string }) => { if (watched.current.has(e.topic)) setWatchErrs(w => [...w.filter(x => !x.startsWith(e.topic)), `${e.topic}: ${e.message}`]); });

  // bounded ingestion
  useChannel("sample", (e: SampleEvent) => {
    if (!e.values) return;
    const t = e.t_ns / 1e9;
    for (const s of seriesRef.current) {
      if (s.topic !== e.topic) continue;
      const v = e.values[s.path];
      if (typeof v !== "number") continue;
      let b = bufs.current.get(s.id); if (!b) bufs.current.set(s.id, (b = { t: [], v: [] }));
      b.t.push(t); b.v.push(v);
      if (b.t.length > MAX_PTS || b.t[0] < t - KEEP_S) {
        const cut = Math.max(b.t.length > MAX_PTS ? Math.ceil(MAX_PTS * 0.1) : 0, lower(b.t, t - KEEP_S));
        b.t.splice(0, cut); b.v.splice(0, cut);
      }
    }
  });

  const compute = useCallback((nowS: number) => {
    const to = view ? view.max : nowS, from = view ? view.min : nowS - windowS;
    const cur = seriesRef.current;
    const stats: Record<string, Stat> = {};
    const tables = cur.map(s => {
      const b = bufs.current.get(s.id) ?? { t: [], v: [] };
      const i0 = lower(b.t, from), i1 = upper(b.t, to);
      const v = b.v.slice(i0, i1);
      stats[s.id] = { latest: b.v.length ? b.v[b.v.length - 1] : null, n: v.length, min: v.length ? Math.min(...v) : null, max: v.length ? Math.max(...v) : null, avg: v.length ? v.reduce((a, c) => a + c, 0) / v.length : null };
      return [b.t.slice(i0, i1), v] as uPlot.AlignedData;
    });
    const data = cur.length ? uPlot.join(tables) : ([[]] as uPlot.AlignedData);
    setFrame({ data, xRange: [from, to], stats });
  }, [view, windowS]);

  useEffect(() => { compute(Date.now() / 1000); }, [compute, series, paused]);
  useEffect(() => {
    if (paused) return;
    const h = setInterval(() => compute(Date.now() / 1000), 250);
    return () => clearInterval(h);
  }, [paused, compute]);

  const add = (f: FieldInfo, path: string) => {
    if (series.some(s => s.topic === topic && s.path === path)) return;
    const id = `${topic}|${path}`;
    setSeries(s => [...s, { id, topic, path, type: f.type, label: `${topic}:${path}`, color: COLORS[s.length % COLORS.length] }]);
    setIdx(null);
  };
  const remove = (id: string) => { setSeries(s => s.filter(x => x.id !== id)); bufs.current.delete(id); };
  const clear = () => { bufs.current.clear(); compute(Date.now() / 1000); };
  const pan = (dir: -1 | 1) => {
    const [a, b] = frame.xRange ?? [Date.now() / 1000 - windowS, Date.now() / 1000];
    const d = (b - a) * 0.25 * dir; setView({ min: a + d, max: b + d }); setPaused(true);
  };
  const exportCsv = () => {
    const cur = series; if (!cur.length) return;
    const tables = cur.map(s => { const b = bufs.current.get(s.id) ?? { t: [], v: [] }; return [b.t, b.v] as uPlot.AlignedData; });
    const j = uPlot.join(tables);
    const rows = [["time_iso", "time_epoch_s", ...cur.map(s => JSON.stringify(s.label))].join(",")];
    for (let i = 0; i < j[0].length; i++) rows.push([new Date((j[0][i] as number) * 1000).toISOString(), (j[0][i] as number).toFixed(6), ...cur.map((_, k) => j[k + 1][i] ?? "")].join(","));
    const url = URL.createObjectURL(new Blob([rows.join("\n")], { type: "text/csv" }));
    const a = document.createElement("a"); a.href = url; a.download = `signals_${new Date().toISOString().replace(/[:.]/g, "-")}.csv`; a.click(); URL.revokeObjectURL(url);
  };

  const plotSeries = useMemo(() => series.map(s => ({ label: s.label, color: s.color })), [series]);
  const fields = (detail?.fields ?? []).filter(f => f.path.toLowerCase().includes(filter.toLowerCase()));
  const sel = series.find(s => s.id === selId);
  const st = sel ? frame.stats[sel.id] : null;

  useDock(!sel ? <p className="muted">Select a series in the table to see its details.</p> : <>
    <div className="kv tight"><span className="muted">Topic</span><span className="mono">{sel.topic}</span>
      <span className="muted">Field</span><span className="mono">{sel.path}</span><span className="muted">Type</span><span className="mono">{sel.type}</span>
      <span className="muted">Samples in view</span><span className="mono">{st?.n ?? 0}</span><span className="muted">Buffered</span><span className="mono">{bufs.current.get(sel.id)?.t.length ?? 0} / {MAX_PTS}</span>
      <span className="muted">Sampling cap</span><span className="mono">{rate} Hz</span></div>
    <p className="muted">Buffers keep the last {KEEP_S / 60} minutes (max {MAX_PTS.toLocaleString()} points per series) and reset when you leave this page.</p></>,
    [sel?.id, st?.n, rate]);

  return (
    <div className="page">
      <h1>Signals</h1>
      <p className="sub">Plot numeric message fields from any topic. Topics are subscribed only while they have a series here.</p>
      <Gate>
        {watchErrs.map(w => <Notice key={w} kind="err">{w}</Notice>)}
        <div className="split">
          <div>
            <div className="row2"><input list="sigtopics" className="mono" placeholder="Topic, e.g. /odom" value={topic} onChange={e => setTopic(e.target.value)} style={{ width: "100%" }} aria-label="Topic" />
              <datalist id="sigtopics">{graph.data?.topics.map(t => <option key={t.name} value={t.name}>{t.types.join(", ")}</option>)}</datalist></div>
            {detailErr && <Notice kind="err">{detailErr}</Notice>}
            {detail?.fields_error && <Notice kind="warn">{detail.fields_error}</Notice>}
            {detail && !detail.fields_error && <>
              <input type="search" placeholder={`Filter ${detail.fields.length} numeric fields…`} value={filter} onChange={e => setFilter(e.target.value)} style={{ marginBottom: 6 }} />
              <div className="list">
                {fields.length === 0 && <div className="empty">{detail.fields.length ? "No fields match." : "This message type has no numeric fields."}</div>}
                {fields.map(f => <div className="item" key={f.path}>
                  <span className="p mono">{f.path}</span><span className="muted mono">{f.type}</span>
                  {f.needs_index
                    ? (idx?.path === f.path
                      ? <><input className="mono" style={{ width: 52 }} value={idx.value} onChange={e => setIdx({ path: f.path, value: e.target.value.replace(/\D/g, "") })} autoFocus placeholder="index" />
                        <button disabled={idx.value === ""} onClick={() => add(f, f.path.split("[]").join(`[${idx.value}]`))}>Add</button></>
                      : <button onClick={() => setIdx({ path: f.path, value: "0" })} title="Array element: choose an index">＋[ ]</button>)
                    : <button onClick={() => add(f, f.path)} disabled={series.some(s => s.topic === topic && s.path === f.path)}>＋</button>}
                </div>)}
              </div></>}
            {!topic && <Empty title="Choose a topic">Pick a topic, then add numeric fields to plot.</Empty>}
          </div>
          <div style={{ overflow: "auto" }}>
            <div className="row2">
              <button onClick={() => { setPaused(p => !p); }}>{paused ? "▶ Resume" : "⏸ Pause"}</button>
              <button onClick={clear}>Clear</button>
              <label className="muted">Window <select value={windowS} onChange={e => { setWindowS(Number(e.target.value)); setView(null); }}>{WINDOWS.map(w => <option key={w} value={w}>{w >= 60 ? `${w / 60} min` : `${w} s`}</option>)}</select></label>
              <label className="muted">Sampling <select value={rate} onChange={e => setRate(Number(e.target.value))}>{RATES.map(r => <option key={r} value={r}>{r} Hz</option>)}</select></label>
              <button onClick={() => pan(-1)} title="Pan back">◀</button><button onClick={() => pan(1)} title="Pan forward">▶</button>
              <button onClick={() => { setView(null); setPaused(false); }} disabled={!view && !paused}>Live / reset</button>
              <span className="spacer" /><button onClick={exportCsv} disabled={!series.length}>Export CSV</button>
            </div>
            {series.length === 0 ? <Empty title="No series yet">Select a topic and add one or more numeric fields. Drag on the plot to zoom; double-click to reset.</Empty> : <>
              <div className="plotbox">
                <Plot key={plotSeries.map(s => s.label).join("|")} series={plotSeries} data={frame.data} xRange={frame.xRange} height={300}
                  onZoom={(a, b) => { setView({ min: a, max: b }); setPaused(true); }} onReset={() => { setView(null); setPaused(false); }} />
              </div>
              <table>
                <thead><tr><th></th><th>Label</th><th style={{ textAlign: "right" }}>Latest</th><th style={{ textAlign: "right" }}>Min</th><th style={{ textAlign: "right" }}>Max</th><th style={{ textAlign: "right" }}>Avg</th><th style={{ textAlign: "right" }}>n</th><th></th></tr></thead>
                <tbody>{series.map(s => { const x = frame.stats[s.id]; return (
                  <tr key={s.id} className={selId === s.id ? "sel" : ""} onClick={() => setSelId(s.id)}>
                    <td><span className="swatch" style={{ background: s.color, display: "inline-block" }} /></td>
                    <td><input value={s.label} style={{ width: "100%" }} onChange={e => setSeries(all => all.map(y => y.id === s.id ? { ...y, label: e.target.value } : y))} aria-label="Series label" /></td>
                    <td className="r mono">{fmtNum(x?.latest, 4)}</td><td className="r mono">{fmtNum(x?.min, 4)}</td><td className="r mono">{fmtNum(x?.max, 4)}</td><td className="r mono">{fmtNum(x?.avg, 4)}</td><td className="r mono">{x?.n ?? 0}</td>
                    <td><button onClick={e => { e.stopPropagation(); remove(s.id); }} title="Remove series">✕</button></td></tr>); })}</tbody>
              </table>
              <p className="muted">Min/Max/Avg cover the visible time range; Latest is the newest buffered value. {paused ? "Display is frozen; collection continues." : ""}</p></>}
          </div>
        </div>
      </Gate>
    </div>);
}
