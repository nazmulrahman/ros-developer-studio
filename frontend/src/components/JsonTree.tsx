import { useState } from "react";

function Leaf({ v }: { v: unknown }) {
  if (typeof v === "number") return <span className="num">{String(v)}</span>;
  if (typeof v === "boolean") return <span className="bool">{String(v)}</span>;
  if (typeof v === "string") return <span className="str">"{v}"</span>;
  return <span className="muted">{String(v)}</span>;
}

function Node({ k, v, depth }: { k: string | null; v: unknown; depth: number }) {
  const [open, setOpen] = useState(depth < 2);
  const label = k !== null ? <span className="key">{k}: </span> : null;
  if (v === null || typeof v !== "object") return <div className="row">{label}<Leaf v={v} /></div>;
  const o = v as Record<string, unknown>;
  if ("__bytes__" in o) return <div className="row">{label}<span className="muted">&lt;{String(o.__bytes__)} bytes&gt;</span></div>;
  const truncated = "__truncated__" in o;
  const isArr = Array.isArray(v) || truncated;
  const items: [string, unknown][] = truncated ? (o.items as unknown[]).map((x, i) => [String(i), x])
    : Array.isArray(v) ? v.map((x, i) => [String(i), x]) : Object.entries(o);
  const count = truncated ? Number(o.__truncated__) : items.length;
  return (
    <div>
      <div className="row toggle" onClick={() => setOpen(!open)}>
        <span className="caret">{open ? "▾" : "▸"}</span>{label}
        <span className="muted">{isArr ? `[${count}]` : `{${items.length}}`}{truncated ? ` — showing first ${items.length}` : ""}</span>
      </div>
      {open && <div className="kids">{items.map(([kk, vv]) => <Node key={kk} k={isArr ? `[${kk}]` : kk} v={vv} depth={depth + 1} />)}</div>}
    </div>);
}
export const JsonTree = ({ value }: { value: unknown }) => <div className="tree mono"><Node k={null} v={value} depth={0} /></div>;
