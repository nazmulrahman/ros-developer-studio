import { PAGES } from "../pages/pages";
import { Icon } from "./Icon";

export function Sidebar({ page, onPage, collapsed, onToggle, host, agentOk }:
  { page: string; onPage: (id: string) => void; collapsed: boolean; onToggle: () => void; host?: string; agentOk: boolean }) {
  return (
    <div className={"sidebar" + (collapsed ? " collapsed" : "")}>
      <div className="logo"><span className="mark"><Icon name="graph" size={18} /></span>{!collapsed && <span>ROS Studio</span>}</div>
      <nav aria-label="Sections">
        {PAGES.map(p => (
          <button key={p.id} className="nav-item" title={p.title}
            aria-current={page === p.id ? "page" : undefined} onClick={() => onPage(p.id)}>
            <Icon name={p.icon} size={18} />{!collapsed && <span>{p.title}</span>}
          </button>))}
      </nav>
      <div className="user" title={host ? `Host: ${host}` : "No host connected"}>
        <span className="avatar"><Icon name="cpu" size={18} /><i className={"dot " + (agentOk ? "ok" : "err")} /></span>
        {!collapsed && <span className="who"><strong>{host ?? "No host"}</strong><small>{agentOk ? "Agent connected" : "Agent offline"}</small></span>}
      </div>
      <div className="foot"><button onClick={onToggle} aria-label="Toggle sidebar" title={collapsed ? "Expand sidebar" : "Collapse sidebar"}><Icon name={collapsed ? "chevronsRight" : "chevronsLeft"} />{!collapsed && <span>Collapse</span>}</button></div>
    </div>);
}
