import { useEffect, useState } from "react";
import { Gate } from "../components/Gate";
import { Gauge, MiniBars, Ring, ShareBars } from "../components/Dash";
import { Notice } from "../components/ui";
import { api } from "../services/api";
import { fmtBytes, fmtDur, fmtHz } from "../services/format";
import { useChannel, useLive } from "../services/live";
import type { AppDiag, HostSample } from "../types/api";

interface SubRow { topic: string; watchers: number; count: number }

export function OverviewPage() {
  const { status, graph, events, watchHost } = useLive();
  const [host, setHost] = useState<HostSample | null>(null);
  const [cpuHist, setCpuHist] = useState<number[]>([]);
  const [subs, setSubs] = useState<SubRow[] | null>(null);
  const [diag, setDiag] = useState<AppDiag | null>(null);
  const connected = status?.agent.state === "connected";
  const ros = status?.ros;

  useEffect(() => { if (!connected) return; watchHost(2); return () => watchHost(null); }, [connected, watchHost]);
  useChannel("host", (e: HostSample) => { setHost(e); if (e.cpu.percent != null) setCpuHist(h => [...h.slice(-13), e.cpu.percent as number]); });
  useEffect(() => {
    if (!connected) { setSubs(null); setDiag(null); return; }
    const poll = () => { api<SubRow[]>("/api/live/subscriptions").then(setSubs).catch(() => {}); api<AppDiag>("/api/app/diagnostics").then(setDiag).catch(() => {}); };
    poll(); const h = setInterval(poll, 5000); return () => clearInterval(h);
  }, [connected]);

  const g = graph.data;
  const counts = g ? [["Nodes", g.nodes.length], ["Topics", g.topics.length], ["Services", g.services.length], ["Actions", g.actions.length]] as [string, number][] : null;
  const total = counts ? counts.reduce((a, [, n]) => a + n, 0) : 0;
  const share = (counts ?? [["Nodes", null], ["Topics", null], ["Services", null], ["Actions", null]] as [string, number | null][])
    .map(([label, count]) => ({ label, count, pct: count != null && total ? (count / total) * 100 : 0 }));
  const cpu = host?.cpu.percent ?? null;

  return (
    <div className="page">
      <h1>Overview</h1>
      <p className="sub">Summary of the connected ROS 2 environment and this tool.</p>
      <Gate needsRos={false}>
        {ros && !ros.available && <Notice kind="err">ROS environment unavailable on the agent host: {ros.error}</Notice>}
        {ros?.discovery === "error" && <Notice kind="err">ROS discovery error: {ros.discovery_error}</Notice>}
        <div className="dash">
          <div className="dash-main">
            <div className="dash-top">
              <section className="conn-card" aria-label="ROS environment">
                <div className="conn-head"><strong>ROS 2</strong><span className="status ok">Agent connected</span></div>
                <div className="conn-line mono">{ros?.available ? `${ros.distro ?? "unknown"} · domain ${ros.domain_id ?? "0"}` : "environment unavailable"}</div>
                <div className="conn-foot"><span>{status?.host?.name ?? "host"}</span><span>{ros?.rmw ? `RMW ${ros.rmw}` : `agent v${status?.agent.version ?? "?"}`}</span></div>
              </section>
              <section className="card stat" aria-label="Topics">
                <h2>Topics</h2>
                <div className="stat-val mono">{g ? g.topics.length : "—"}</div>
                <p className="muted">{g ? `${g.nodes.length} nodes · ${g.services.length} services · ${g.actions.length} actions` : "Waiting for the ROS graph…"}</p>
                <p className="muted">{ros?.available ? `Discovery ${ros.discovery}` : ""}</p>
              </section>
            </div>
            <section className="card">
              <h2>Active topic monitoring</h2>
              {!subs || subs.length === 0 ? <div className="muted">No topics are being monitored. Open one in the Topic Inspector or Signals.</div> :
                <table><thead><tr><th>Topic</th><th style={{ textAlign: "right" }}>Viewers</th><th style={{ textAlign: "right" }}>Messages</th></tr></thead>
                  <tbody>{subs.map(s => <tr key={s.topic}><td className="mono">{s.topic}</td><td className="r mono">{s.watchers}</td><td className="r mono">{s.count}</td></tr>)}</tbody></table>}
            </section>
            <div className="dash-pair">
              <section className="card"><h2>This tool's resource use</h2>
                {!diag ? <div className="muted">Waiting…</div> : <div className="kv tight">
                  <span className="muted">Backend memory</span><span className="mono">{fmtBytes(diag.backend.rss_bytes)}</span><span className="muted">Backend CPU</span><span className="mono">{fmtHz(diag.backend.cpu_percent)} %</span>
                  <span className="muted">Agent memory</span><span className="mono">{diag.agent ? fmtBytes(diag.agent.rss_bytes) : "—"}</span><span className="muted">Agent CPU</span><span className="mono">{diag.agent ? `${fmtHz(diag.agent.cpu_percent)} %` : "—"}</span>
                  <span className="muted">Dropped events</span><span className="mono">{diag.backend.dropped_events + (diag.agent?.dropped_events ?? 0)}</span><span className="muted">Agent uptime</span><span className="mono">{diag.agent ? fmtDur(diag.agent.uptime_s) : "—"}</span></div>}</section>
              <section className="card"><h2>Recent application events</h2>
                {events.length === 0 ? <div className="muted">No warnings or errors since this page loaded.</div> :
                  <div className="evlist">{events.slice(0, 10).map((e, i) => <div className={"e " + e.level} key={i}><span className="mono muted">{new Date(e.t).toLocaleTimeString([], { hour12: false })}</span><span>{e.text}</span></div>)}</div>}
                <p className="muted" style={{ marginBottom: 0 }}>Agent, discovery and subscription events of this tool. ROS log inspection is available in Diagnostics.</p></section>
            </div>
          </div>
          <div className="dash-side">
            <section className="card"><h2>Graph composition</h2><ShareBars items={share} /></section>
            <section className="card gauge-card">
              <h2>Host CPU</h2><p className="muted">{host ? host.host.name : "Waiting for host data…"}</p>
              <Gauge value={cpu} label="Host CPU" /><MiniBars values={cpuHist} />
            </section>
            <section className="card ring-card">
              <h2>Host memory</h2>
              <Ring value={host?.memory.percent} text={host ? `${host.memory.percent.toFixed(0)}%` : "—"} sub={host ? `${fmtBytes(host.memory.used)} of ${fmtBytes(host.memory.total)}` : undefined} />
            </section>
          </div>
        </div>
      </Gate>
    </div>);
}
