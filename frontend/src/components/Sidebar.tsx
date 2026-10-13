import { PAGES } from "../pages/pages";
import { Icon } from "./Icon";

export function Sidebar({ page, onPage, collapsed, onToggle }:
  { page: string; onPage: (id: string) => void; collapsed: boolean; onToggle: () => void }) {
  return (
    <div className={"sidebar" + (collapsed ? " collapsed" : "")}>
      <nav aria-label="Sections">
        {PAGES.map(p => (
          <button key={p.id} className="nav-item" title={p.title}
            aria-current={page === p.id ? "page" : undefined} onClick={() => onPage(p.id)}>
            <Icon name={p.icon} />{!collapsed && <span>{p.title}</span>}
          </button>))}
      </nav>
      <div className="foot"><button onClick={onToggle} aria-label="Toggle sidebar" title={collapsed ? "Expand sidebar" : "Collapse sidebar"}><Icon name={collapsed ? "chevronsRight" : "chevronsLeft"} />{!collapsed && <span>Collapse</span>}</button></div>
    </div>);
}
