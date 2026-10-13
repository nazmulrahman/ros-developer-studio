import { useEffect, useRef, useState } from "react";
import { FieldPicker, validPath, type Mapping } from "../components/FieldPicker";
import { Gate } from "../components/Gate";
import { Empty, Notice } from "../components/ui";
import { Plot } from "../plots/Plot";
import { useDock } from "../services/app";
import { useChannel, useLive } from "../services/live";
import { usePreferences, useSaved, STORE_KEYS } from "../services/preferences";
import { appendPoint, finite, mappingList, type MotionWidget, type Point } from "../visualizations/model";
import type { SampleEvent } from "../types/api";

const blank = { topic: "", path: "" };
export function MotionPage() {
  const { watch, unwatch, status, wsState } = useLive(); const prefs = usePreferences();
  const [widgets, setWidgets, storageError] = useSaved(STORE_KEYS.motion, mappingList, [] as MotionWidget[]);
  const [label, setLabel] = useState(""); const [unit, setUnit] = useState("");
  const [measured, setMeasured] = useState<Mapping>(blank); const [reference, setReference] = useState<Mapping>(blank);
  const [compare, setCompare] = useState(false); const [paused, setPaused] = useState(false); const [errors, setErrors] = useState<Record<string, string>>({});
  const buffers = useRef<Record<string, Point[]>>({}); const [frame, setFrame] = useState<Record<string, Point[]>>({});
  const [now, setNow] = useState(Date.now() / 1000);
  useDock(<p className="muted">Map any numeric feedback field. Add one widget per motor, wheel, encoder, pose coordinate or status value. Optional reference fields overlay commanded values. Choose matching units; no conversions or time alignment are assumed. Plots use agent receive time.</p>, []);
  useEffect(() => {
    const topics = new Map<string, Set<string>>();
    widgets.forEach(w => [w.measured, w.reference].forEach(m => { if (m) { if (!topics.has(m.topic)) topics.set(m.topic, new Set()); topics.get(m.topic)!.add(m.path); } }));
    topics.forEach((fields, topic) => watch(topic, { hz: prefs.motion_hz, fields: [...fields] }));
    return () => topics.forEach((_, topic) => unwatch(topic));
  }, [widgets, prefs.motion_hz, watch, unwatch]);
  useEffect(() => { if (wsState !== "open" || status?.agent.state !== "connected" || status.mode !== "live") { buffers.current = {}; setFrame({}); } }, [wsState, status?.agent.state, status?.mode]);
  useEffect(() => { const ids = new Set(widgets.map(w => w.id)); for (const id of Object.keys(buffers.current)) if (!ids.has(id)) delete buffers.current[id]; }, [widgets]);
  useEffect(() => { const timer = window.setInterval(() => { if (!paused) { setFrame({ ...buffers.current }); setNow(Date.now() / 1000); } }, 250); return () => clearInterval(timer); }, [paused]);
  useChannel("sample", (ev: SampleEvent) => {
    widgets.forEach(w => [w.measured, w.reference].forEach((m, i) => { if (m?.topic === ev.topic) buffers.current[w.id] = appendPoint(buffers.current[w.id] ?? [], { t: ev.t_ns / 1e9, value: finite(ev.values?.[m.path]), reference: i === 1 }); }));
    setErrors(e => e[ev.topic] ? { ...e, [ev.topic]: "" } : e);
  });
  useChannel("watch_error", (e: { topic: string; message: string }) => setErrors(all => ({ ...all, [e.topic]: e.message })));
  const canAdd = label.trim() && measured.topic && validPath(measured.path) && (!compare || (reference.topic && validPath(reference.path))) && widgets.length < 16;
  return <div className="page"><h1>Motion</h1><p className="sub">Configurable feedback and command comparisons · receive time · 60 seconds / 1,200 points per widget.</p>
    {storageError && <Notice kind="warn">{storageError}</Notice>}<Gate><form className="card" onSubmit={e => { e.preventDefault(); if (!canAdd) return; setWidgets([...widgets, { id: crypto.randomUUID(), label: label.trim(), unit: unit.trim(), measured, reference: compare ? reference : null }]); setLabel(""); }}>
      <div className="row2"><label>Label <input aria-label="Widget label" value={label} maxLength={80} onChange={e => setLabel(e.target.value)} placeholder="Motor feedback" /></label><label>Unit <input aria-label="Widget unit" value={unit} maxLength={24} onChange={e => setUnit(e.target.value)} placeholder="RPM, m/s, rad/s…" /></label><label><input type="checkbox" checked={compare} onChange={e => setCompare(e.target.checked)} />Compare with command / reference</label></div>
      <div className="mapping-grid"><FieldPicker label="Measured" value={measured} onChange={setMeasured} />{compare && <FieldPicker label="Reference" value={reference} onChange={setReference} />}</div><button disabled={!canAdd}>Add feedback widget</button>
    </form><div className="row2"><button onClick={() => setPaused(p => !p)}>{paused ? "Resume display" : "Pause display"}</button><span className="muted">{paused ? "Display frozen; collection continues." : "Only mapped topics are subscribed."}</span></div>
    {!widgets.length && <Empty title="Map a feedback signal">Select discovered topics and numeric fields above. No robot geometry or motor count is assumed.</Empty>}
    <div className="charts">{widgets.map(w => {
      const points = (frame[w.id] ?? []).filter(p => p.t >= now - 60); const latest = [...points].reverse().find(p => !p.reference);
      const command = [...points].reverse().find(p => p.reference); const stale = !latest || now - latest.t > prefs.stale_after_s;
      const times = [...new Set(points.map(p => p.t))].sort((a, b) => a - b);
      const values = new Map(points.filter(p => !p.reference).map(p => [p.t, p.value])); const refs = new Map(points.filter(p => p.reference).map(p => [p.t, p.value]));
      const series = [{ label: "Measured", color: "#49B6E8" }, ...(w.reference ? [{ label: "Reference", color: "#F5AD57" }] : [])];
      return <div className="card" key={w.id}><div className="row2"><strong>{w.label}</strong><span className="spacer" /><button aria-label={`Remove ${w.label}`} onClick={() => setWidgets(all => all.filter(x => x.id !== w.id))}>Remove</button></div>
        <div className="motion-value mono">{latest?.value == null ? "—" : latest.value.toFixed(3)} <small>{w.unit}</small></div><p className="muted">{!latest ? "Waiting for samples" : stale ? `Stale · last sample ${(now - latest.t).toFixed(1)} s ago` : "Receiving"}{latest?.value === null ? " · missing or non-finite field" : ""}</p>
        {w.reference && <p className="muted">Reference: {command?.value == null ? "—" : command.value.toFixed(3)} {w.unit}{command && now - command.t > prefs.stale_after_s ? " · stale" : ""}</p>}
        {[w.measured, w.reference].map((m, i) => m && <div className="mono muted" key={i}>{m.topic} → {m.path}{errors[m.topic] && <Notice kind="err">{errors[m.topic]}</Notice>}</div>)}
        <Plot series={series} data={[times, times.map(t => values.get(t) ?? null), ...(w.reference ? [times.map(t => refs.get(t) ?? null)] : [])]} xRange={[now - 60, now]} height={180} yLabel={w.unit} />
      </div>;
    })}</div></Gate></div>;
}
