import { useEffect, useState } from "react";
import { api } from "../services/api";
import { Notice } from "./ui";
export function Parameters({ name }: { name: string }) {
  const [data, setData] = useState<{ parameters: { name: string; type: number; value: unknown }[]; truncated: boolean } | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [version, setVersion] = useState(0);
  const [filter, setFilter] = useState("");
  useEffect(() => {
    let active = true; setData(null); setError(""); setBusy(true);
    api<typeof data>(`/api/live/parameters?name=${encodeURIComponent(name)}`).then(d => { if (active) setData(d); })
      .catch(e => { if (active) setError(e.message); }).finally(() => { if (active) setBusy(false); });
    return () => { active = false; };
  }, [name, version]);
  return <><h2>Parameters · read only</h2><div className="row2"><input aria-label="Filter parameters" placeholder="Filter parameters" value={filter} onChange={e => setFilter(e.target.value)} /><button disabled={busy} onClick={() => setVersion(v => v + 1)}>Refresh</button></div>
    {busy && <p>Reading parameters…</p>}{error && <Notice kind="warn">{error}</Notice>}
    {data?.truncated && <Notice kind="warn">Showing the first 500 parameters.</Notice>}
    {data && data.parameters.length === 0 && <p className="muted">No parameters returned.</p>}
    {data?.parameters.filter(p => p.name.includes(filter)).map(p => <div className="ep" key={p.name}><strong>{p.name}</strong><div className="mono" style={{ overflowWrap: "anywhere" }}>{JSON.stringify(p.value)}</div></div>)}</>;
}
