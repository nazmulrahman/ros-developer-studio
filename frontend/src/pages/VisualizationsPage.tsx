import { useEffect, useState } from "react";
import { Gate } from "../components/Gate";
import { Empty, Notice } from "../components/ui";
import { useDock } from "../services/app";
import { useChannel, useLive } from "../services/live";
import { STORE_KEYS, usePreferences, useSaved } from "../services/preferences";
import { SensorView } from "../visualizations/SensorView";
import { SUPPORTED, visualList, type NormalizedSample, type VisualWidget } from "../visualizations/model";

export function VisualizationsPage() {
  const { graph, watch, unwatch, status, wsState } = useLive(); const prefs = usePreferences();
  const [widgets, setWidgets, storageError] = useSaved(STORE_KEYS.visualizations, visualList, [] as VisualWidget[]);
  const [topic, setTopic] = useState(""); const [paused, setPaused] = useState(false);
  const [samples, setSamples] = useState<Record<string, NormalizedSample>>({});
  const [errors, setErrors] = useState<Record<string, string>>({}); const [now, setNow] = useState(Date.now()); const [epoch, setEpoch] = useState(0);
  const topics = graph.data?.topics.filter(t => t.types.some(x => SUPPORTED.includes(x))) ?? [];
  useDock(<p className="muted">Select supported topics from discovery. Camera previews are capped at 640 × 480, LiDAR at 2,048 rays and previews at 5 Hz. Renderers consume source-labelled samples with separate header, receive and recording timestamps; bag playback will use these in Phase 4.</p>, []);
  useEffect(() => { widgets.forEach(w => watch(w.topic, { hz: prefs.preview_hz, visual: true })); return () => widgets.forEach(w => unwatch(w.topic)); }, [widgets, prefs.preview_hz, watch, unwatch]);
  useEffect(() => { if (wsState !== "open" || status?.agent.state !== "connected" || status.mode !== "live") { setSamples({}); setEpoch(e => e + 1); } }, [wsState, status?.agent.state, status?.mode]);
  useEffect(() => { const ids = new Set(widgets.map(w => w.topic)); setSamples(s => Object.fromEntries(Object.entries(s).filter(([k]) => ids.has(k)))); }, [widgets]);
  useEffect(() => { const timer = window.setInterval(() => setNow(Date.now()), 500); return () => clearInterval(timer); }, []);
  useChannel("sample", (e: NormalizedSample) => { if (e.visual && widgets.some(w => w.topic === e.topic)) { if (!paused) setSamples(all => ({ ...all, [e.topic]: e })); setErrors(all => all[e.topic] ? { ...all, [e.topic]: "" } : all); } });
  useChannel("watch_error", (e: { topic: string; message: string }) => setErrors(all => ({ ...all, [e.topic]: e.message })));
  return <div className="page"><h1>Visualizations</h1><p className="sub">Sensor previews from explicitly selected topics.</p>{storageError && <Notice kind="warn">{storageError}</Notice>}<Gate>
    <div className="row2"><select aria-label="Sensor topic" value={topic} onChange={e => setTopic(e.target.value)}><option value="">Select a supported sensor topic</option>{topics.map(t => <option key={t.name} value={t.name}>{t.name} · {t.types.join(", ")}</option>)}</select>
      <button disabled={!topic || widgets.some(w => w.topic === topic) || widgets.length >= 8} onClick={() => { const t = topics.find(t => t.name === topic); if (t) setWidgets([...widgets, { id: crypto.randomUUID(), topic, type: t.types.find(x => SUPPORTED.includes(x))! }]); }}>Add viewer</button>
      <button onClick={() => setPaused(p => !p)}>{paused ? "Resume display" : "Pause display"}</button></div>
    {paused && <Notice>Display frozen; subscription statistics continue.</Notice>}{!widgets.length && <Empty title="Choose a sensor topic">Camera, LaserScan, IMU, battery, odometry, Twist, TF and ROS diagnostic messages are supported. No topics are subscribed automatically.</Empty>}
    <div className="charts">{widgets.map(w => { const sample = samples[w.topic]; const age = sample ? Math.max(0, (now - Number(sample.stamps.receive_ns) / 1e6) / 1000) : null;
      return <div className="card" key={w.id}><div className="row2"><strong className="mono">{w.topic}</strong><span className="spacer" /><button onClick={() => setWidgets(all => all.filter(x => x.id !== w.id))}>Remove</button></div><p className="muted">{w.type}</p>
        {errors[w.topic] && <Notice kind="err">{errors[w.topic]}</Notice>}{!sample ? <Empty title="Waiting for messages" /> : <><div className="muted">{paused ? "Paused" : age !== null && age > prefs.stale_after_s ? "Stale preview" : "Live preview"} · {age?.toFixed(1)} s since receipt</div><SensorView key={`${epoch}:${w.id}`} sample={sample} /><details><summary>Sample clocks and source</summary><div className="mono">Source: {sample.source_id}<br />Mode: {sample.source_mode}<br />Header ns: {sample.stamps.header_ns ?? "not provided"}<br />Receive ns: {sample.stamps.receive_ns ?? "not provided"}<br />Record ns: {sample.stamps.record_ns ?? "not recorded"}</div></details></>}
      </div>;
    })}</div></Gate></div>;
}
