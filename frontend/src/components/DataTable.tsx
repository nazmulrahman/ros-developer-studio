import { useMemo, useState, type ReactNode } from "react";

export interface Col<T> { key: string; label: string; get: (r: T) => string | number | null | undefined; mono?: boolean; right?: boolean; width?: number | string; render?: (r: T) => ReactNode }
const MAX_ROWS = 500;

export function DataTable<T>({ cols, rows, rowKey, selected, onSelect, onOpen, emptyText, placeholder, toolbar, initialSort }: {
  cols: Col<T>[]; rows: T[]; rowKey: (r: T) => string; selected?: string | null; onSelect?: (r: T) => void; onOpen?: (r: T) => void;
  emptyText: string; placeholder?: string; toolbar?: ReactNode; initialSort?: string;
}) {
  const [q, setQ] = useState("");
  const [sort, setSort] = useState<{ key: string; dir: 1 | -1 }>({ key: initialSort ?? cols[0].key, dir: 1 });
  const view = useMemo(() => {
    const needle = q.trim().toLowerCase();
    let r = needle ? rows.filter(x => cols.some(c => String(c.get(x) ?? "").toLowerCase().includes(needle))) : rows.slice();
    const col = cols.find(c => c.key === sort.key);
    if (col) r.sort((a, b) => {
      const x = col.get(a), y = col.get(b);
      if (x == null) return y == null ? 0 : 1; if (y == null) return -1;
      return (typeof x === "number" && typeof y === "number" ? x - y : String(x).localeCompare(String(y))) * sort.dir;
    });
    return r;
  }, [rows, q, sort, cols]);
  return (
    <div className="tablewrap">
      <div className="toolbar">
        <input type="search" placeholder={placeholder ?? "Search…"} value={q} onChange={e => setQ(e.target.value)} aria-label="Search table" />
        <span className="muted">{view.length === rows.length ? `${rows.length} rows` : `${view.length} of ${rows.length}`}</span>
        <span className="spacer" />{toolbar}
      </div>
      <div className="tablescroll">
        <table>
          <thead><tr>{cols.map(c => (
            <th key={c.key} style={{ width: c.width, textAlign: c.right ? "right" : "left" }} className="sortable"
              onClick={() => setSort(s => ({ key: c.key, dir: s.key === c.key ? (s.dir === 1 ? -1 : 1) : 1 }))}>
              {c.label}{sort.key === c.key ? (sort.dir === 1 ? " ▲" : " ▼") : ""}</th>))}</tr></thead>
          <tbody>
            {view.slice(0, MAX_ROWS).map(r => (
              <tr key={rowKey(r)} className={selected === rowKey(r) ? "sel" : ""} onClick={() => onSelect?.(r)} onDoubleClick={() => onOpen?.(r)}>
                {cols.map(c => <td key={c.key} className={(c.mono ? "mono " : "") + (c.right ? "r" : "")}>{c.render ? c.render(r) : (c.get(r) ?? "—")}</td>)}
              </tr>))}
          </tbody>
        </table>
        {view.length === 0 && <div className="empty">{rows.length === 0 ? emptyText : "No rows match the filter."}</div>}
        {view.length > MAX_ROWS && <div className="empty">Showing first {MAX_ROWS} rows — refine the search.</div>}
      </div>
    </div>);
}
