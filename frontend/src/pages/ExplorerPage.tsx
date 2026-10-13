import { useEffect, useMemo, useState } from "react";
import { Icon } from "../components/Icon";
import { DataTable, type Col } from "../components/DataTable";
import { Gate } from "../components/Gate";
import { Empty, Notice } from "../components/ui";
import { api } from "../services/api";
import { useApp, useDock } from "../services/app";
import { useLive } from "../services/live";
import type { Endpoint, GraphIface, GraphNode, GraphTopic, NodeDetail, TopicDetail } from "../types/api";

import { Parameters } from "../components/Parameters";

type Tab = "topics" | "nodes" | "services" | "actions";

function EndpointList({ title, eps }: { title: string; eps: Endpoint[] }) {
  return (<>
    <h2>{title} ({eps.length})</h2>
    {eps.length === 0 && <div className="muted" style={{ marginBottom: 8 }}>None</div>}
    {eps.map((e, i) => (
      <div className="ep mono" key={i}>{e.namespace.replace(/\/$/, "")}/{e.node}
        <div className="muted">{e.qos.reliability ?? "?"} · {e.qos.durability ?? "?"} · {e.qos.history ?? "?"}{e.qos.depth != null ? `(${e.qos.depth})` : ""}</div></div>))}
  </>);
}

function TopicDock({ name, onInspect }: { name: string; onInspect: () => void }) {
  const [d, setD] = useState<TopicDetail | null>(null); const [err, setErr] = useState<string | null>(null);
  const { graph } = useLive();
  useEffect(() => { setD(null); setErr(null); api<TopicDetail>(`/api/live/topic?name=${encodeURIComponent(name)}`).then(setD).catch(e => setErr(String(e.message ?? e))); }, [name, graph.updated]);
  return (<>
    <div className="mono" style={{ wordBreak: "break-all", marginBottom: 6 }}>{name}</div>
    <button onClick={onInspect} style={{ marginBottom: 8 }}>Open in Topic Inspector</button>
    {err && <Notice kind="err">{err}</Notice>}
    {!d && !err && <div className="muted">Loading…</div>}
    {d && <>
      <div className="kv tight"><span className="muted">Type</span><span className="mono">{d.types.join(", ")}</span>
        <span className="muted">Publishers</span><span className="mono">{d.publishers.length}</span>
        <span className="muted">Subscribers</span><span className="mono">{d.subscribers.length}</span>
        <span className="muted">Numeric fields</span><span className="mono">{d.fields_error ? "unavailable" : d.fields.length}</span></div>
      {d.fields_error && <Notice kind="warn">{d.fields_error}</Notice>}
      {d.qos_conflicts.length > 0 && <Notice kind="warn">QoS incompatibilities in the graph:
        {d.qos_conflicts.map((c, i) => <div key={i} className="mono">{c.subscriber} ← {c.publisher}: {c.reason}</div>)}</Notice>}
      <EndpointList title="Publishers" eps={d.publishers} /><EndpointList title="Subscribers" eps={d.subscribers} />
    </>}
  </>);
}

function NodeDock({ name }: { name: string }) {
  const [d, setD] = useState<NodeDetail | null>(null); const [err, setErr] = useState<string | null>(null);
  useEffect(() => { setD(null); setErr(null); api<NodeDetail>(`/api/live/node?name=${encodeURIComponent(name)}`).then(setD).catch(e => setErr(String(e.message ?? e))); }, [name]);
  const L = ({ t, rows }: { t: string; rows: GraphIface[] }) => (<><h2>{t} ({rows.length})</h2>{rows.map(r => <div key={r.name} className="mono" style={{ marginBottom: 4 }}>{r.name}<div className="muted">{r.types.join(", ")}</div></div>)}</>);
  return (<><div className="mono" style={{ marginBottom: 8 }}>{name}</div>{err && <Notice kind="err">{err}</Notice>}{!d && !err && <div className="muted">Loading…</div>}
    {d && <><L t="Publishes" rows={d.publishers} /><L t="Subscribes" rows={d.subscribers} /><L t="Services served" rows={d.service_servers} /><L t="Service clients" rows={d.service_clients} /><Parameters key={name} name={name} /></>}</>);
}

export function ExplorerPage() {
  const { graph, refreshGraph } = useLive();
  const { setPage, setSelectedTopic, selectedTopic } = useApp();
  const [tab, setTab] = useState<Tab>("topics");
  const [sel, setSel] = useState<{ tab: Tab; key: string } | null>(null);
  const g = graph.data;

  useDock(!sel ? <p className="muted">Select a topic, node, service or action to see its details.</p>
    : sel.tab === "topics" ? <TopicDock name={sel.key} onInspect={() => { setSelectedTopic(sel.key); setPage("inspector"); }} />
    : sel.tab === "nodes" ? <NodeDock name={sel.key} />
    : <div className="mono">{sel.key}<div className="muted">{(sel.tab === "services" ? g?.services : g?.actions)?.find(x => x.name === sel.key)?.types.join(", ")}</div></div>,
    [sel, g?.services, g?.actions]);

  const topicCols: Col<GraphTopic>[] = useMemo(() => [
    { key: "name", label: "Topic", get: r => r.name, mono: true }, { key: "type", label: "Type", get: r => r.types.join(", "), mono: true },
    { key: "pubs", label: "Pubs", get: r => r.publishers, right: true, mono: true, width: 60 },
    { key: "subs", label: "Subs", get: r => r.subscribers, right: true, mono: true, width: 60 }], []);
  const nodeCols: Col<GraphNode>[] = useMemo(() => [
    { key: "name", label: "Node", get: r => r.name, mono: true }, { key: "ns", label: "Namespace", get: r => r.namespace, mono: true },
    { key: "full", label: "Full name", get: r => r.full + (r.self ? "  (this agent)" : ""), mono: true }], []);
  const ifaceCols: Col<GraphIface>[] = useMemo(() => [
    { key: "name", label: "Name", get: r => r.name, mono: true }, { key: "type", label: "Type", get: r => r.types.join(", "), mono: true }], []);

  const toolbar = <>
    {graph.loading && <span className="muted">Refreshing…</span>}
    {graph.updated && !graph.loading && <span className="muted">updated {new Date(graph.updated).toLocaleTimeString([], { hour12: false })}</span>}
    <button onClick={refreshGraph}><Icon name="refresh" />Refresh</button></>;
  const empty = "No entries discovered. The agent is connected; ROS discovery can take a moment, and this environment may simply have none.";

  return (
    <div className="page">
      <h1>ROS Explorer</h1>
      <p className="sub">Live graph from the connected ROS 2 environment. Updates automatically when the graph changes.</p>
      <Gate>
        {graph.error && <Notice kind="err">Graph query failed: {graph.error}</Notice>}
        {g?.warnings.map((w, i) => <Notice key={i} kind="warn">{w}</Notice>)}
        {!g && !graph.error && <Empty title="Discovering…" />}
        {g && <>
          <div className="seg" style={{ marginBottom: 8, alignSelf: "flex-start" }} role="tablist">
            {([["topics", g.topics.length], ["nodes", g.nodes.length], ["services", g.services.length], ["actions", g.actions.length]] as [Tab, number][]).map(([t, n]) =>
              <button key={t} aria-pressed={tab === t} onClick={() => { setTab(t); setSel(null); }}>{t[0].toUpperCase() + t.slice(1)} ({n})</button>)}
          </div>
          {tab === "topics" && <DataTable cols={topicCols} rows={g.topics} rowKey={r => r.name} selected={sel?.tab === "topics" ? sel.key : null} toolbar={toolbar}
            placeholder="Filter by topic name or message type…" emptyText={empty} onSelect={r => setSel({ tab: "topics", key: r.name })}
            onOpen={r => { setSelectedTopic(r.name); setPage("inspector"); }} />}
          {tab === "nodes" && <DataTable cols={nodeCols} rows={g.nodes} rowKey={r => r.full} selected={sel?.tab === "nodes" ? sel.key : null} toolbar={toolbar}
            placeholder="Filter nodes…" emptyText={empty} onSelect={r => setSel({ tab: "nodes", key: r.full })} />}
          {tab === "services" && <DataTable cols={ifaceCols} rows={g.services} rowKey={r => r.name} selected={sel?.tab === "services" ? sel.key : null} toolbar={toolbar}
            placeholder="Filter services…" emptyText={empty} onSelect={r => setSel({ tab: "services", key: r.name })} />}
          {tab === "actions" && <DataTable cols={ifaceCols} rows={g.actions} rowKey={r => r.name} selected={sel?.tab === "actions" ? sel.key : null} toolbar={toolbar}
            placeholder="Filter actions…" emptyText={empty} onSelect={r => setSel({ tab: "actions", key: r.name })} />}
          <div className="muted" style={{ marginTop: 4 }}>Double-click a topic to open it in the Topic Inspector.{selectedTopic ? ` Current inspector topic: ${selectedTopic}` : ""}</div>
        </>}
      </Gate>
    </div>);
}
