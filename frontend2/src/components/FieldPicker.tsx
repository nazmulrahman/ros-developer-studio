import { useEffect, useId, useState } from "react";
import { useLive } from "../services/live";
import { api, topicApi } from "../services/api";
import type { TopicDetail } from "../types/api";
import { Notice } from "./ui";
export interface Mapping { topic: string; path: string }
export const validPath = (path: string) => /^[A-Za-z_]\w*(?:\[\d+\]|\.[A-Za-z_]\w*)*$/.test(path);
export function FieldPicker({ label, value, onChange }: { label: string; value: Mapping; onChange: (v: Mapping) => void }) {
  const { graph } = useLive(); const id = useId();
  const [detail, setDetail] = useState<TopicDetail | null>(null); const [error, setError] = useState("");
  useEffect(() => { let active = true; setDetail(null); setError(""); if (value.topic) topicApi<TopicDetail>(value.topic).then(d => { if (active) setDetail(d); }).catch(e => { if (active) setError(e.message); }); return () => { active = false; }; }, [value.topic, graph.updated]);
  return <fieldset className="mapping"><legend>{label}</legend><label>Topic <select aria-label={`${label} topic`} value={value.topic} onChange={e => onChange({ topic: e.target.value, path: "" })}><option value="">Select discovered topic</option>{graph.data?.topics.map(t => <option key={t.name} value={t.name}>{t.name}</option>)}</select></label>
    <label>Numeric field <input aria-label={`${label} field`} list={id} placeholder="Select field; replace [] with an index" value={value.path} onChange={e => onChange({ ...value, path: e.target.value })} /></label>
    <datalist id={id}>{detail?.fields.map(f => <option key={f.path} value={f.path} />)}</datalist>
    {error && <Notice kind="err">{error}</Notice>}{detail?.fields_error && <Notice kind="warn">{detail.fields_error}</Notice>}
    {value.path && !validPath(value.path) && <span className="muted">Use a complete field path, with array indexes such as data[0].</span>}</fieldset>;
}
