import { PAGES } from "../pages/pages";

export function Sidebar({ page, onPage, collapsed, onToggle }:
  { page: string; onPage: (id: string) => void; collapsed: boolean; onToggle: () => void }) {
  return (
    <div className={"sidebar" + (collapsed ? " collapsed" : "")}>
      <nav aria-label="Sections">
        {PAGES.map(p => (
          <button key={p.id} className="nav-item" title={p.title}
            aria-current={page === p.id ? "page" : undefined} onClick={() => onPage(p.id)}>
            <span className="ico">{p.icon}</span>{!collapsed && <span>{p.title}</span>}
          </button>))}
      </nav>
      <div className="foot"><button onClick={onToggle} aria-label="Toggle sidebar" style={{ width: "100%" }}>{collapsed ? "»" : "« Collapse"}</button></div>
    </div>);
}
