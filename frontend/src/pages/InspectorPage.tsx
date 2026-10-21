import { useEffect, useRef, useState } from "react";
import { Icon } from "../components/Icon";
import { Gate } from "../components/Gate";
import { JsonTree } from "../components/JsonTree";
import { Empty, Notice, StatusBadge, Tile } from "../components/ui";
import { api, topicApi } from "../services/api";
import { useApp, useDock } from "../services/app";
import { fmtBps, fmtBytes, fmtClock, fmtDur, fmtHz, fmtNum } from "../services/format";
import { useChannel, useLive } from "../services/live";
import type { Endpoint, SampleEvent, TopicDetail, TopicStatsEvent } from "../types/api";

const RATES = [1, 2, 5, 10, 20];

function Eps({ title, eps }: { title: string; eps: Endpoint[] }) {
  return (<><h2>{title} ({eps.length})</h2>{eps.length === 0 && <div className="muted" style={{ marginBottom: 8 }}>None</div>}
    {eps.map((e, i) => <div className="ep mono" key={i}>{e.namespace.replace(/\/$/, "")}/{e.node}
      <div className="muted">{e.qos.reliability ?? "?"} · {e.qos.durability ?? "?"} · {e.qos.history ?? "?"}{e.qos.depth != null ? `(${e.qos.depth})` : ""}</div></div>)}</>);
}

export function InspectorPage() {
  const { graph, watch, unwatch, status } = useLive();
  const { selectedTopic, setSelectedTopic } = useApp();
  const [input, setInput] = useState(selectedTopic ?? "");
  const [detail, setDetail] = useState<TopicDetail | null>(null);
  const [detailErr, setDetailErr] = useState<string | null>(null);
  const [stats, setStats] = useState<TopicStatsEvent | null>(null);
  const [msg, setMsg] = useState<SampleEvent | null>(null);
  const [paused, setPaused] = useState(false);
  const [rate, setRate] = useState(5);
  const [watchErr, setWatchErr] = useState<string | null>(null);
  const [now, setNow] = useState(Date.now());
  const pausedRef = useRef(paused); pausedRef.current = paused;
  const topic = selectedTopic;
  const known = graph.data?.topics.some(t => t.name === topic);

  // subscribe only while a topic is selected and this page is open
  useEffect(() => {
    setStats(null); setMsg(null); setWatchErr(null); setDetail(null); setDetailErr(null);
    if (!topic) return;
    topicApi<TopicDetail>(topic).then(setDetail).catch(e => setDetailErr(String(e.message ?? e)));
    return () => unwatch(topic);
  }, [topic, unwatch]);
  useEffect(() => { if (topic) watch(topic, { hz: rate, payload: true }); }, [topic, rate, watch, status?.agent.state]);
  useEffect(() => { if (topic && known) topicApi<TopicDetail>(topic).then(setDetail).catch(() => {}); }, [graph.updated]); // eslint-disable-line
  useEffect(() => { const t = setInterval(() => setNow(Date.now()), 500); return () => clearInterval(t); }, []);

  useChannel("source_reset", () => setMsg(null));
  useChannel("sample_missing", (e: {topic:string}) => {if(e.topic===topic) setMsg(null);});
  useChannel("sample", (e: SampleEvent) => { if (e.topic === topic && !pausedRef.current) setMsg(e); });
  useChannel("stats", (e: TopicStatsEvent) => { if (e.topic === topic) setStats(e); });
  useChannel("watch_error", (e: { topic: string; code: string; message: string }) => { if (e.topic === topic) setWatchErr(`${e.message}`); });

  const s = stats?.stats;
  const tone = stats?.status === "receiving" ? "ok" : stats?.status === "stalled" || stats?.status === "publisher_no_data" ? "warn" : stats && stats.status !== "unknown" ? "err" : undefined;
  const since = s?.last_recv_ns ? (now - s.last_recv_ns / 1e6) / 1000 : s?.since_last_s;
  const headerStamp = (() => { const st = (msg?.payload as any)?.header?.stamp; return st && typeof st.sec === "number" ? `${st.sec}.${String(st.nanosec ?? 0).padStart(9, "0")}` : null; })();

  useDock(!topic ? <p className="muted">Pick a topic to see message metadata and QoS.</p> : <>
    <div className="mono" style={{ wordBreak: "break-all", marginBottom: 6 }}>{topic}</div>
    {detailErr && <Notice kind="err">{detailErr}</Notice>}
    {detail && <>
      <div className="kv tight"><span className="muted">Type</span><span className="mono">{detail.types.join(", ")}</span>
        <span className="muted">Latest msg size</span><span className="mono">{fmtBytes(s?.last_size_bytes)}</span>
        <span className="muted">Receive stamp</span><span className="mono">{fmtClock(msg?.t_ns)}</span>
        <span className="muted">Header stamp</span><span className="mono">{headerStamp ?? "none / not in message"}</span>
        <span className="muted">Numeric fields</span><span className="mono">{detail.fields_error ? "unavailable" : detail.fields.length}</span></div>
      {detail.fields_error && <Notice kind="warn">{detail.fields_error}</Notice>}
      {detail.qos_conflicts.length > 0 && <Notice kind="warn">QoS incompatibilities between graph endpoints (these subscribers will not receive data):
        {detail.qos_conflicts.map((c, i) => <div key={i} className="mono">{c.subscriber} ← {c.publisher}: {c.reason}</div>)}</Notice>}
      <Eps title="Publishers" eps={detail.publishers} /><Eps title="Subscribers" eps={detail.subscribers} />
      <p className="muted">This inspector subscribes with BEST_EFFORT/VOLATILE QoS, which is compatible with every publisher, so measurement itself never fails on QoS.</p>
    </>}</>, [topic, detail, detailErr, s?.last_size_bytes, msg?.t_ns, headerStamp]);

  return (
    <div className="page">
      <h1>Topic Inspector</h1>
      <p className="sub">Live messages, measured frequency and QoS for one topic. The topic is subscribed only while this page shows it.</p>
      <Gate>
        <div className="row2">
          <input list="topics" placeholder="Topic name, e.g. /scan" value={input} onChange={e => setInput(e.target.value)} className="mono" style={{ width: 320 }}
            onKeyDown={e => { if (e.key === "Enter") setSelectedTopic(input.trim() || null); }} onBlur={() => { if (input.trim() !== (topic ?? "")) setSelectedTopic(input.trim() || null); }} aria-label="Topic" />
          <datalist id="topics">{graph.data?.topics.map(t => <option key={t.name} value={t.name}>{t.types.join(", ")}</option>)}</datalist>
          {topic && <button onClick={() => { setInput(""); setSelectedTopic(null); }}>Stop monitoring</button>}
        </div>
        {!topic && <Empty title="No topic selected">Choose one from the list above, or double-click a topic in ROS Explorer.</Empty>}
        {topic && graph.data && !known && <Notice kind="warn">{topic} is not currently in the ROS graph.</Notice>}
        {watchErr && <Notice kind="err">Cannot subscribe: {watchErr}</Notice>}
        {topic && <>
          <div className="tiles">
            <Tile label="Status" value={stats ? <StatusBadge status={stats.status} /> : <span className="muted">measuring…</span>} sub={stats?.evidence} tone={tone} />
            <Tile label="Frequency" value={`${fmtHz(s?.hz)} Hz`} sub={`avg since start ${fmtHz(s?.avg_hz)} Hz`} />
            <Tile label="Period" value={`${fmtNum(s?.period_ms, 1)} ms`} sub={`jitter ±${fmtNum(s?.jitter_ms, 1)} ms`} />
            <Tile label="Bandwidth" value={fmtBps(s?.bandwidth_bps)} sub={`last msg ${fmtBytes(s?.last_size_bytes)}`} />
            <Tile label="Messages" value={s ? s.count.toLocaleString() : "—"} sub={`window ${s?.window_s ?? "—"} s · ${s?.samples_in_window ?? 0} samples`} />
            <Tile label="Last received" value={fmtClock(s?.last_recv_ns)} sub={`${fmtDur(since)} ago`} />
            <Tile label="Publishers / Subs" value={stats ? `${stats.publishers} / ${stats.subscribers}` : "—"} sub="excluding this tool" />
          </div>
          <div className="row2">
            <button onClick={() => setPaused(p => !p)}><Icon name={paused ? "play" : "pause"} />{paused ? "Resume" : "Pause"}</button>
            <button onClick={() => navigator.clipboard.writeText(JSON.stringify(msg?.payload ?? null, null, 2))} disabled={!msg}><Icon name="copy" />Copy message</button>
            <button onClick={() => setMsg(null)} disabled={!msg}><Icon name="trash" />Clear</button>
            <label className="muted">Update rate <select value={rate} onChange={e => setRate(Number(e.target.value))}>{RATES.map(r => <option key={r} value={r}>{r} Hz</option>)}</select></label>
            <span className="muted">{paused ? "Display frozen — frequency and counts keep updating." : ""}</span>
          </div>
          {msg ? <JsonTree value={msg.payload} /> : <Empty title={stats?.status === "no_publisher" ? "No publisher on this topic" : stats && stats.stats.count === 0 ? "No messages received yet" : "Waiting for a message…"}>
            {stats?.evidence}</Empty>}
        </>}
      </Gate>
    </div>);
}
