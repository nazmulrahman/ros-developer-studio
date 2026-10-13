import { useEffect, useState } from "react";
import { Gate } from "../components/Gate";
import { Notice, Tile } from "../components/ui";
import { api } from "../services/api";
import { fmtBytes, fmtDur, fmtHz } from "../services/format";
import { useChannel, useLive } from "../services/live";
import type { AppDiag, HostSample } from "../types/api";

interface SubRow { topic: string; watchers: number; count: number }

export function OverviewPage() {
  const { status, graph, events, watchHost } = useLive();
  const [host, setHost] = useState<HostSample | null>(null);
  const [subs, setSubs] = useState<SubRow[] | null>(null);
  const [diag, setDiag] = useState<AppDiag | null>(null);
  const connected = status?.agent.state === "connected";
  const ros = status?.ros;

  useEffect(() => { if (!connected) return; watchHost(2); return () => watchHost(null); }, [connected, watchHost]);
  useChannel("host", (e: HostSample) => setHost(e));
  useEffect(() => {
    if (!connected) { setSubs(null); setDiag(null); return; }
    const poll = () => { api<SubRow[]>("/api/live/subscriptions").then(setSubs).catch(() => {}); api<AppDiag>("/api/app/diagnostics").then(setDiag).catch(() => {}); };
    poll(); const h = setInterval(poll, 5000); return () => clearInterval(h);
  }, [connected]);

  const g = graph.data;
  return (
    <div className="page">
      <h1>Overview</h1>
      <p className="sub">Summary of the connected ROS 2 environment and this tool.</p>
      <Gate needsRos={false}>
        {ros && !ros.available && <Notice kind="err">ROS environment unavailable on the agent host: {ros.error}</Notice>}
        {ros?.discovery === "error" && <Notice kind="err">ROS discovery error: {ros.discovery_error}</Notice>}
        <div className="tiles">
          <Tile label="Agent" value="connected" tone="ok" sub={`v${status?.agent.version ?? "?"} · ${status?.host?.name ?? ""}`} />
          <Tile label="ROS distribution" value={ros?.available ? ros.distro ?? "unknown" : "unavailable"} tone={ros?.available ? undefined : "err"} sub={ros?.rmw ? `RMW ${ros.rmw}` : undefined} />
          <Tile label="ROS domain ID" value={ros?.available ? ros.domain_id ?? "0" : "—"} sub={ros?.available ? `discovery ${ros.discovery}` : undefined} />
          <Tile label="Nodes" value={g ? g.nodes.length : "—"} /><Tile label="Topics" value={g ? g.topics.length : "—"} />
          <Tile label="Services" value={g ? g.services.length : "—"} /><Tile label="Actions" value={g ? g.actions.length : "—"} />
          <Tile label="Host CPU" value={host?.cpu.percent != null ? `${host.cpu.percent.toFixed(1)} %` : "—"} sub={host ? host.host.name : undefined} />
          <Tile label="Host RAM" value={host ? `${host.memory.percent.toFixed(1)} %` : "—"} sub={host ? `${fmtBytes(host.memory.used)} of ${fmtBytes(host.memory.total)}` : undefined} />
        </div>
        <div className="charts">
          <div className="card"><h2>Active topic monitoring</h2>
            {!subs || subs.length === 0 ? <div className="muted">No topics are being monitored. Open one in the Topic Inspector or Signals.</div> :
              <table><thead><tr><th>Topic</th><th style={{ textAlign: "right" }}>Viewers</th><th style={{ textAlign: "right" }}>Messages</th></tr></thead>
                <tbody>{subs.map(s => <tr key={s.topic}><td className="mono">{s.topic}</td><td className="r mono">{s.watchers}</td><td className="r mono">{s.count}</td></tr>)}</tbody></table>}</div>
          <div className="card"><h2>This tool's resource use</h2>
            {!diag ? <div className="muted">Waiting…</div> : <div className="kv tight">
              <span className="muted">Backend memory</span><span className="mono">{fmtBytes(diag.backend.rss_bytes)}</span><span className="muted">Backend CPU</span><span className="mono">{fmtHz(diag.backend.cpu_percent)} %</span>
              <span className="muted">Agent memory</span><span className="mono">{diag.agent ? fmtBytes(diag.agent.rss_bytes) : "—"}</span><span className="muted">Agent CPU</span><span className="mono">{diag.agent ? `${fmtHz(diag.agent.cpu_percent)} %` : "—"}</span>
              <span className="muted">Dropped events</span><span className="mono">{diag.backend.dropped_events + (diag.agent?.dropped_events ?? 0)}</span><span className="muted">Agent uptime</span><span className="mono">{diag.agent ? fmtDur(diag.agent.uptime_s) : "—"}</span></div>}</div>
          <div className="card"><h2>Recent application events</h2>
            {events.length === 0 ? <div className="muted">No warnings or errors since this page loaded.</div> :
              <div className="evlist">{events.slice(0, 10).map((e, i) => <div className={"e " + e.level} key={i}><span className="mono muted">{new Date(e.t).toLocaleTimeString([], { hour12: false })}</span><span>{e.text}</span></div>)}</div>}
            <p className="muted" style={{ marginBottom: 0 }}>Agent, discovery and subscription events of this tool. ROS log (/rosout) inspection arrives in phase 5.</p></div>
        </div>
      </Gate>
    </div>);
}
