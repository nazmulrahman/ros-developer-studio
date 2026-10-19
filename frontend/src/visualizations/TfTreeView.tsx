import { useMemo, useState } from "react";
import { Background, BackgroundVariant, Controls, MarkerType, MiniMap, ReactFlow, ReactFlowProvider, type Edge, type Node } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { Empty, Notice, Tile } from "../components/ui";
import { autoLayout } from "../packageExplorer/layout";
import { orientation, type TfEdge, type TfSnapshot } from "./model";

const fmt = (value: unknown, digits = 3) => typeof value === "number" && Number.isFinite(value) ? value.toFixed(digits) : "—";

function Canvas({ snapshot, selected, onSelect, search }: { snapshot: TfSnapshot; selected: TfEdge | null; onSelect: (edge: TfEdge | null) => void; search: string }) {
  const { nodes, edges } = useMemo(() => {
    const query = search.trim().toLowerCase();
    const nodeRows: Node[] = snapshot.frames.map((frame, i) => ({ id: frame, position: { x: 0, y: i * 80 }, data: { label: frame }, className: `tf-frame ${snapshot.roots.includes(frame) ? "root" : ""} ${query && !frame.toLowerCase().includes(query) ? "dim" : ""}` }));
    const edgeRows: Edge[] = snapshot.edges.map(edge => ({ id: edge.id, source: edge.parent, target: edge.child, label: edge.static ? "static" : edge.stale ? `${edge.age_s.toFixed(1)}s stale` : undefined,
      markerEnd: { type: MarkerType.ArrowClosed }, animated: !edge.static && !edge.stale,
      style: { stroke: edge.id === selected?.id ? "#FF4F6E" : edge.stale || !edge.valid_rotation ? "#FF5C64" : edge.static ? "#B58CFF" : "#6A7192", strokeWidth: edge.id === selected?.id ? 2.5 : 1.4, strokeDasharray: edge.static ? "5 3" : undefined }, data: { tf: edge } }));
    return { nodes: autoLayout(nodeRows, edgeRows, "LR"), edges: edgeRows };
  }, [snapshot, selected?.id, search]);
  return <div className="tf-canvas"><ReactFlow nodes={nodes} edges={edges} fitView minZoom={.1} maxZoom={2.5} nodesDraggable nodesConnectable={false} elementsSelectable onEdgeClick={(_, edge) => onSelect((edge.data as { tf?: TfEdge } | undefined)?.tf ?? null)} onPaneClick={() => onSelect(null)}>
    <Background variant={BackgroundVariant.Dots} gap={18} size={1} color="#444963" /><MiniMap pannable zoomable nodeColor={n => n.className?.toString().includes("root") ? "#3DDC97" : "#FF4F6E"} maskColor="rgba(8,9,15,.72)" /><Controls showInteractive={false} />
  </ReactFlow></div>;
}

function View({ snapshot }: { snapshot: TfSnapshot }) {
  const [selected, setSelected] = useState<TfEdge | null>(null); const [search, setSearch] = useState("");
  const attitude = selected ? orientation(selected.transform?.rotation) : null;
  return <div className="tf-workspace"><div className="tf-toolbar"><input type="search" value={search} onChange={e => setSearch(e.target.value)} placeholder="Find a frame…" /><span>{snapshot.frames.length} frames · {snapshot.edges.length} transforms · {snapshot.components.length} groups</span></div>
    <div className="tiles"><Tile label="Roots" value={snapshot.roots.length} /><Tile label="Disconnected groups" value={snapshot.components.length} tone={snapshot.components.length > 1 ? "warn" : undefined} /><Tile label="Stale dynamic" value={snapshot.edges.filter(e => e.stale).length} tone={snapshot.edges.some(e => e.stale) ? "warn" : undefined} /><Tile label="Problems" value={snapshot.diagnostics.length} tone={snapshot.diagnostics.some(d => d.severity === "error") ? "err" : snapshot.diagnostics.length ? "warn" : "ok"} /></div>
    {snapshot.diagnostics.slice(0, 8).map((finding, i) => <Notice key={`${finding.code}:${i}`} kind={finding.severity === "error" ? "err" : "warn"}>{finding.message}</Notice>)}
    {!snapshot.frames.length ? <Empty title="Waiting for transforms">The viewer is subscribed to all discovered TFMessage topics, including /tf and /tf_static.</Empty> : <Canvas snapshot={snapshot} selected={selected} onSelect={setSelected} search={search} />}
    {selected && <div className="tf-selection"><strong className="mono">{selected.parent} → {selected.child}</strong><span>{selected.static ? "Static" : selected.stale ? "Stale dynamic" : "Dynamic"} · {selected.topic} · received {selected.age_s.toFixed(1)} s ago</span><span className="mono">Translation: x {fmt(selected.transform?.translation?.x)} · y {fmt(selected.transform?.translation?.y)} · z {fmt(selected.transform?.translation?.z)} m</span><span className="mono">Rotation: roll {fmt(attitude?.roll, 1)}° · pitch {fmt(attitude?.pitch, 1)}° · yaw {fmt(attitude?.yaw, 1)}°</span></div>}
    {snapshot.edges.length >= snapshot.limit && <Notice kind="warn">The TF model reached its {snapshot.limit}-edge safety limit.</Notice>}
  </div>;
}

export function TfTreeView({ snapshot }: { snapshot: TfSnapshot }) { return <ReactFlowProvider><View snapshot={snapshot} /></ReactFlowProvider>; }
