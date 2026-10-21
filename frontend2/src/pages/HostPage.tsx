import { useEffect, useRef, useState } from "react";
import { Gate } from "../components/Gate";
import { Notice, Tile } from "../components/ui";
import { Plot } from "../plots/Plot";
import { api } from "../services/api";
import { useDock } from "../services/app";
import { fmtBps, fmtBytes, fmtDur, fmtNum } from "../services/format";
import { useChannel, useLive } from "../services/live";
import type { HostSample } from "../types/api";

const HIST = 300, INTERVALS = [0.5, 1, 2, 5];
type Key = "cpu" | "memory" | "disk" | "network" | "temperature" | "gpu";
interface Hist { t: number[]; cpu: number[]; mem: number[]; rx: (number | null)[]; tx: (number | null)[]; temp: (number | null)[]; gpu: (number | null)[]; gtemp: (number | null)[] }
const empty = (): Hist => ({ t: [], cpu: [], mem: [], rx: [], tx: [], temp: [], gpu: [], gtemp: [] });
const NA = <span className="unavail" title="Not reported by this host">Unavailable</span>;

export function HostPage() {
  const { watchHost, status } = useLive();
  const [interval, setIntervalS] = useState(1);
  const [last, setLast] = useState<HostSample | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [sel, setSel] = useState<Key>("cpu");
  const [, bump] = useState(0);
  const hist = useRef<Hist>(empty());

  const ingest = (e: HostSample) => {
    const h = hist.current, t = e.t_ns / 1e9;
    if (h.t.length && t <= h.t[h.t.length - 1]) return;
    h.t.push(t); h.cpu.push(e.cpu.percent ?? NaN); h.mem.push(e.memory.percent); h.rx.push(e.network.rx_bps == null ? null : e.network.rx_bps / 1e6);
    h.tx.push(e.network.tx_bps == null ? null : e.network.tx_bps / 1e6); h.temp.push(e.temperature_c); h.gpu.push(e.gpu?.util_percent ?? null); h.gtemp.push(e.gpu?.temp_c ?? null);
    if (h.t.length > HIST) for (const k of Object.keys(h) as (keyof Hist)[]) h[k].splice(0, h.t.length - HIST);
    setLast(e); bump(x => x + 1);
  };
  useEffect(() => { if (status?.agent.state === "connected") api<HostSample>("/api/host/metrics").then(ingest).catch(e => setErr(String(e.message ?? e))); }, [status?.agent.state]);
  useEffect(() => { watchHost(interval); return () => watchHost(null); }, [interval, watchHost, status?.agent.state]);
  useChannel("host", ingest);
  useChannel("host_error", (e: { error: string }) => setErr(e.error));

  const h = hist.current, n = h.t.length;
  const xr: [number, number] | null = n >= 2 ? [h.t[Math.max(0, n - HIST)], h.t[n - 1]] : null;
  const tile = (k: Key, label: string, value: React.ReactNode, sub?: React.ReactNode) => (
    <div onClick={() => setSel(k)} style={{ cursor: "pointer", outline: sel === k ? "1px solid var(--accent)" : "none", borderRadius: 4 }}><Tile label={label} value={value} sub={sub} /></div>);
  const chart = (title: string, series: { label: string; color: string; v: (number | null)[] }[], unit: string) => (
    <div className="plotbox" key={title}><div className="t">{title} <span className="muted">({unit})</span></div>
      <Plot key={series.map(s => s.label).join("|")} series={series.map(s => ({ label: s.label, color: s.color }))} data={[h.t, ...series.map(s => s.v)] as any} xRange={xr} height={150} /></div>);

  useDock(!last ? null : <>
    <div className="kv tight"><span className="muted">Host</span><span className="mono">{last.host.name}</span><span className="muted">OS</span><span className="mono">{last.host.os}</span>
      <span className="muted">Machine</span><span className="mono">{last.host.machine}</span><span className="muted">Logical cores</span><span className="mono">{last.host.cores}</span></div>
    <h2>{sel}</h2>
    {sel === "cpu" && <div className="kv tight"><span className="muted">Frequency</span><span className="mono">{last.cpu.freq_mhz ? `${last.cpu.freq_mhz.toFixed(0)} MHz` : "Unavailable"}</span>
      <span className="muted">Load avg 1/5/15</span><span className="mono">{last.cpu.load_avg ? last.cpu.load_avg.map(x => x.toFixed(2)).join(" / ") : "Unavailable"}</span></div>}
    {sel === "memory" && <div className="kv tight"><span className="muted">RAM used</span><span className="mono">{fmtBytes(last.memory.used)} / {fmtBytes(last.memory.total)}</span>
      <span className="muted">Swap used</span><span className="mono">{fmtBytes(last.swap.used)} / {fmtBytes(last.swap.total)}</span></div>}
    {sel === "disk" && (last.disk ? <div className="kv tight"><span className="muted">Path</span><span className="mono">{last.disk.path}</span><span className="muted">Used</span><span className="mono">{fmtBytes(last.disk.used)}</span>
      <span className="muted">Free</span><span className="mono">{fmtBytes(last.disk.free)}</span><span className="muted">Total</span><span className="mono">{fmtBytes(last.disk.total)}</span></div> : <p className="muted">Unavailable</p>)}
    {sel === "network" && <p className="muted">Throughput is the sum over all interfaces, measured between samples.</p>}
    {sel === "temperature" && (Object.keys(last.temperatures).length ? <div className="kv tight">{Object.entries(last.temperatures).map(([k, v]) => <><span className="muted" key={k}>{k}</span><span className="mono">{v.toFixed(1)} °C</span></>)}</div> : <p className="muted">No temperature sensors reported by this host.</p>)}
    {sel === "gpu" && (last.gpu ? <div className="kv tight"><span className="muted">Source</span><span className="mono">{last.gpu.source}</span></div> : <p className="muted">No supported GPU interface found (tried nvidia-smi and Jetson sysfs).</p>)}
  </>, [sel, last?.t_ns]);

  return (
    <div className="page">
      <h1>Host Metrics</h1>
      <p className="sub">{last ? <>Monitoring <strong className="mono">{last.host.name}</strong> — the machine running the agent, not this browser's computer.</> : "Measurements from the machine running the agent."}</p>
      <Gate needsRos={false}>
        {err && <Notice kind="warn">{err}</Notice>}
        <div className="row2"><label className="muted">Sample interval <select value={interval} onChange={e => setIntervalS(Number(e.target.value))}>{INTERVALS.map(i => <option key={i} value={i}>{i} s</option>)}</select></label>
          <span className="muted">History: last {HIST} samples</span></div>
        {!last ? <div className="muted">Waiting for first sample…</div> : <>
          <div className="tiles">
            {tile("cpu", "CPU", last.cpu.percent == null ? NA : `${last.cpu.percent.toFixed(1)} %`, `${last.cpu.per_core.length} cores`)}
            {tile("memory", "RAM", `${last.memory.percent.toFixed(1)} %`, `${fmtBytes(last.memory.used)} of ${fmtBytes(last.memory.total)}`)}
            {tile("memory", "Swap", last.swap.total ? `${last.swap.percent.toFixed(1)} %` : "none", fmtBytes(last.swap.used))}
            {tile("disk", "Disk", last.disk ? `${last.disk.percent.toFixed(1)} %` : NA, last.disk ? `${fmtBytes(last.disk.free)} free` : undefined)}
            {tile("network", "Network ↓ / ↑", last.network.rx_bps == null ? NA : <>{fmtBps(last.network.rx_bps)}<br />{fmtBps(last.network.tx_bps)}</>)}
            {tile("temperature", "Temperature", last.temperature_c == null ? NA : `${last.temperature_c.toFixed(1)} °C`, "hottest sensor")}
            {tile("gpu", "GPU load", last.gpu?.util_percent == null ? NA : `${last.gpu.util_percent.toFixed(0)} %`, last.gpu ? last.gpu.source : undefined)}
            {tile("gpu", "GPU memory", last.gpu?.mem_used_mib == null ? NA : `${last.gpu.mem_used_mib.toFixed(0)} / ${(last.gpu.mem_total_mib ?? 0).toFixed(0)} MiB`)}
            {tile("gpu", "GPU temp", last.gpu?.temp_c == null ? NA : `${last.gpu.temp_c.toFixed(0)} °C`)}
            <Tile label="Uptime" value={fmtDur(last.uptime_s)} />
          </div>
          <div className="card"><h2>Per-core CPU</h2><div className="bars">{last.cpu.per_core.map((p, i) => <div className="bar" key={i} title={`core ${i}: ${fmtNum(p, 1)}%`}><i style={{ height: `${p}%` }} /><span className="mono">{i}<br />{p.toFixed(0)}%</span></div>)}</div></div>
          <div className="charts">
            {chart("CPU", [{ label: "CPU", color: "#FF4F6E", v: h.cpu }], "%")}
            {chart("Memory", [{ label: "RAM", color: "#3DDC97", v: h.mem }], "%")}
            {chart("Network", [{ label: "Rx", color: "#FF4F6E", v: h.rx }, { label: "Tx", color: "#FFBE3D", v: h.tx }], "Mbit/s")}
            {last.temperature_c != null && chart("Temperature", [{ label: "hottest sensor", color: "#FF5C64", v: h.temp }], "°C")}
            {last.gpu?.util_percent != null && chart("GPU load", [{ label: "GPU", color: "#B58CFF", v: h.gpu }], "%")}
          </div></>}
      </Gate>
    </div>);
}
