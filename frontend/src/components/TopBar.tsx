import { Icon } from "./Icon";
import type { LiveStatus, Mode } from "../types/api";
import type { WsState } from "../services/live";

type Kind = "ok" | "warn" | "err" | "idle";
const Pill = ({ kind, children, title }: { kind: Kind; children: React.ReactNode; title?: string }) =>
  <span className="pill" title={title}><span className={"dot " + (kind === "idle" ? "" : kind)} />{children}</span>;

export function TopBar({ mode, onMode, wsState, status, token, onToken }: {
  mode: Mode; onMode: (m: Mode) => void; wsState: WsState; status: LiveStatus | null; token: string; onToken: (t: string) => void;
}) {
  const be: [Kind, string] = wsState === "open" ? ["ok", "connected"] : wsState === "connecting" ? ["warn", "connecting…"]
    : wsState === "unauthorized" ? ["err", "token rejected"] : wsState === "closed" ? ["err", "unreachable, retrying"] : ["idle", "enter token"];
  const a = status?.agent;
  const ag: [Kind, string] = !a ? ["idle", "unknown"] : a.state === "connected" ? ["ok", `connected${a.version ? " v" + a.version : ""}`]
    : a.state === "connecting" ? ["warn", "connecting…"] : a.state === "disabled" ? ["idle", "not used (offline mode)"] : ["err", "disconnected"];
  const r = status?.ros;
  const ros: [Kind, string] = !a || a.state !== "connected" || !r ? ["idle", "unknown (agent not connected)"]
    : !r.available ? ["err", "environment unavailable"]
    : r.discovery === "error" ? ["err", `${r.distro ?? "?"} · domain ${r.domain_id} · discovery error`]
    : ["ok", `${r.distro ?? "unknown distro"} · domain ${r.domain_id} · discovery active`];
  return (
    <header className="topbar">
      <span className="brand"><Icon name="graph" size={18} />ROS Developer Studio</span>
      <div className="seg" role="group" aria-label="Mode">
        <button aria-pressed={mode === "live"} onClick={() => onMode("live")}>Live</button>
        <button aria-pressed={mode === "offline"} onClick={() => onMode("offline")}>Offline bag</button>
      </div>
      <span className="spacer" />
      {status?.host && <span className="pill mono" title="Host machine running the agent">host: {status.host.name}</span>}
      <Pill kind={be[0]}>Backend: {be[1]}</Pill>
      <Pill kind={ag[0]} title={a?.last_error ?? a?.url ?? ""}>Agent: {ag[1]}</Pill>
      <Pill kind={ros[0]} title={r?.error ?? r?.discovery_error ?? (r?.rmw ? `RMW: ${r.rmw}` : "")}>ROS: {ros[1]}</Pill>
      <input className="mono" type="password" placeholder="access token" value={token} onChange={e => onToken(e.target.value)} style={{ width: 150 }} aria-label="Access token" />
    </header>);
}
