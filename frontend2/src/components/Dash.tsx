import type { ReactNode } from "react";

const clamp = (v: number | null | undefined) => Math.max(0, Math.min(100, v ?? 0));

/** Half-circle gauge, 0–100. */
export function Gauge({ value, label }: { value: number | null | undefined; label: string }) {
  const len = Math.PI * 80, pct = clamp(value);
  return (
    <svg className="gauge" viewBox="0 0 200 118" role="img" aria-label={`${label}: ${value == null ? "no data" : Math.round(pct) + " percent"}`}>
      <path d="M20 100 A80 80 0 0 1 180 100" className="gauge-track" />
      <path d="M20 100 A80 80 0 0 1 180 100" className="gauge-fill" strokeDasharray={`${(len * pct) / 100} ${len}`} />
      <text x="100" y="98" textAnchor="middle" className="gauge-val">{value == null ? "—" : Math.round(pct)}<tspan className="gauge-unit">{value == null ? "" : "%"}</tspan></text>
    </svg>);
}

/** Ring with centred text, 0–100. */
export function Ring({ value, text, sub }: { value: number | null | undefined; text: ReactNode; sub?: ReactNode }) {
  const c = 2 * Math.PI * 56, pct = clamp(value);
  return (
    <div className="ring">
      <svg viewBox="0 0 140 140" role="img" aria-label={value == null ? "no data" : `${Math.round(pct)} percent`}>
        <circle cx="70" cy="70" r="56" className="ring-track" />
        <circle cx="70" cy="70" r="56" className="ring-fill" strokeDasharray={`${(c * pct) / 100} ${c}`} transform="rotate(-90 70 70)" />
      </svg>
      <div className="ring-copy"><strong>{text}</strong>{sub && <small>{sub}</small>}</div>
    </div>);
}

/** Small column chart of recent samples (0–100); the newest bar is highlighted. */
export function MiniBars({ values, slots = 14 }: { values: number[]; slots?: number }) {
  const pad = Array.from({ length: Math.max(0, slots - values.length) }, () => null as number | null);
  const all = [...pad, ...values.slice(-slots)];
  return (
    <div className="minibars" aria-hidden="true">
      {all.map((v, i) => <i key={i} className={v == null ? "empty" : i === all.length - 1 ? "now" : ""} style={{ height: `${v == null ? 8 : Math.max(8, clamp(v))}%` }} />)}
    </div>);
}

/** Labelled share bars; each item is a share of the total. */
export function ShareBars({ items }: { items: { label: string; count: number | null; pct: number }[] }) {
  return (
    <ul className="sharebars">
      {items.map((it, i) => (
        <li key={it.label} className={"c" + i}>
          <div><span>{it.label} <small className="muted mono">{it.count ?? "—"}</small></span><span className="mono">{Math.round(it.pct)}%</span></div>
          <span className="track"><i style={{ width: `${clamp(it.pct)}%` }} /></span>
        </li>))}
    </ul>);
}
