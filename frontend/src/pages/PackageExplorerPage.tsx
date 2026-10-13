import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Background, BackgroundVariant, BaseEdge, Controls, EdgeLabelRenderer, getBezierPath, MarkerType, MiniMap,
  Panel, ReactFlow, ReactFlowProvider, SelectionMode, useEdgesState, useNodesState, useReactFlow,
  type Edge, type EdgeProps, type Node, type OnSelectionChangeParams,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { toPng, toSvg } from "html-to-image";
import { Icon } from "../components/Icon";
import { Empty, Notice, Tile } from "../components/ui";
import { api } from "../services/api";
import { useApp, useDock } from "../services/app";
import { useLive } from "../services/live";
import { autoLayout } from "../packageExplorer/layout";
import { PackageNode, type PackageNodeData } from "../packageExplorer/PackageNode";
import { SourceViewer } from "../packageExplorer/SourceViewer";
import type { NodeDetail } from "../types/api";
import type { DependencyEdge, FolderListing, GraphMode, PackageInfo, PackageLayout, SavedGroup, SourceFile, WorkspaceFile, WorkspaceScan } from "../packageExplorer/types";

const NODE_TYPES = { packageNode: PackageNode };
const MODE_LABELS: Record<GraphMode, string> = { dependencies: "Dependencies", architecture: "Workspace", launch: "Launch", live: "Live ROS", comparison: "Static vs live" };
const COLORS: Record<string, string> = { ament_python: "#49B6E8", ament_cmake: "#34C995", external: "#65788A", launch: "#B58CFF", runtime: "#F5AD57", topic: "#5FC4C8" };

function RelationshipEdge(props: EdgeProps) {
  const [path, x, y] = getBezierPath(props);
  return <><BaseEdge path={path} markerEnd={props.markerEnd} style={props.style} /><EdgeLabelRenderer>{props.label && <div className="pkg-edge-label" style={{ transform: `translate(-50%, -50%) translate(${x}px,${y}px)` }}>{String(props.label)}</div>}</EdgeLabelRenderer></>;
}
const EDGE_TYPES = { relationship: RelationshipEdge };

type Selection = { type: "package"; value: PackageInfo } | { type: "file"; package: PackageInfo; value: WorkspaceFile } | { type: "edge"; value: DependencyEdge } | { type: "runtime"; id: string } | null;

function download(dataUrl: string, name: string) { const a = document.createElement("a"); a.href = dataUrl; a.download = name; a.click(); }
const slug = (value: string) => value.replace(/[^a-z0-9_-]+/gi, "-").replace(/^-|-$/g, "") || "workspace";

interface FileBranch { directories: Record<string, FileBranch>; files: WorkspaceFile[] }
function fileTree(pkg: PackageInfo): FileBranch {
  const root: FileBranch = { directories: {}, files: [] };
  pkg.files.forEach(file => {
    const relative = file.path.startsWith(pkg.path + "/") ? file.path.slice(pkg.path.length + 1) : file.path;
    const parts = relative.split("/"); let branch = root;
    parts.slice(0, -1).forEach(part => { branch = (branch.directories[part] ??= { directories: {}, files: [] }); });
    branch.files.push(file);
  });
  return root;
}
function FileTree({ branch, selected, onFile }: { branch: FileBranch; selected: Selection; onFile: (f: WorkspaceFile) => void }) {
  return <>{Object.entries(branch.directories).sort(([a], [b]) => a.localeCompare(b)).map(([name, child]) => <details key={name} open><summary><Icon name="folder" size={12} />{name}</summary><div className="tree-children"><FileTree branch={child} selected={selected} onFile={onFile} /></div></details>)}
    {branch.files.sort((a, b) => a.name.localeCompare(b.name)).map(file => <button className={`tree-row file ${selected?.type === "file" && selected.value.path === file.path ? "active" : ""}`} key={file.path} title={`${file.path} · ${file.kind}`} onClick={() => onFile(file)}><Icon name={file.kind === "launch" ? "play" : "file"} size={13} /><span>{file.name}</span><em>{file.kind === "metadata" ? "meta" : file.kind.slice(0, 4)}</em></button>)}</>;
}

function TreePackage({ pkg, selected, onPackage, onFile }: { pkg: PackageInfo; selected: Selection; onPackage: () => void; onFile: (f: WorkspaceFile) => void }) {
  const [open, setOpen] = useState(false);
  const tree = useMemo(() => fileTree(pkg), [pkg]);
  return <div className="workspace-package"><button className={`tree-row ${selected?.type === "package" && selected.value.name === pkg.name ? "active" : ""}`} onClick={() => { setOpen(!open); onPackage(); }} onDoubleClick={() => setOpen(true)}><span className="tree-caret">{open ? "▾" : "▸"}</span><Icon name="package" size={14} /><span>{pkg.name}</span><em>{pkg.build_type}</em></button>
    {open && <div className="tree-children"><FileTree branch={tree} selected={selected} onFile={onFile} /></div>}
  </div>;
}

function FolderBrowser({ onClose, onChoose }: { onClose: () => void; onChoose: (path: string) => Promise<void> }) {
  const [listing, setListing] = useState<FolderListing | null>(null); const [loading, setLoading] = useState(true); const [error, setError] = useState("");
  const open = useCallback(async (path?: string) => { setLoading(true); setError(""); try { setListing(await api<FolderListing>(`/api/package-explorer/browse${path ? `?path=${encodeURIComponent(path)}` : ""}`)); } catch (e) { setError(e instanceof Error ? e.message : String(e)); } finally { setLoading(false); } }, []);
  useEffect(() => { void open(); }, [open]);
  return <div className="folder-browser-backdrop" role="presentation" onMouseDown={e => { if (e.target === e.currentTarget) onClose(); }}><section className="folder-browser" role="dialog" aria-modal="true" aria-label="Choose a ROS 2 workspace folder">
    <header><div><h2>Choose workspace folder</h2><p>Browse folders on the computer running ROS Developer Studio.</p></div><button onClick={onClose} aria-label="Close folder browser">×</button></header>
    <div className="folder-locations">{listing?.locations.map(location => <button key={location.path} onClick={() => void open(location.path)}>{location.path}</button>)}</div>
    <div className="folder-path mono"><button disabled={!listing?.parent} onClick={() => listing?.parent && void open(listing.parent)} title="Parent folder"><Icon name="left" /></button><span>{listing?.path ?? "Loading…"}</span></div>
    {error && <Notice kind="err">{error}</Notice>}
    <div className="folder-list">{loading ? <p className="muted">Reading folders…</p> : listing?.directories.map(folder => <button key={folder.path} onDoubleClick={() => void open(folder.path)} onClick={() => void open(folder.path)}><Icon name="folder" /><span>{folder.name}</span>{folder.package && <em>ROS package</em>}<Icon name="right" /></button>)}{!loading && !listing?.directories.length && <p className="muted">This folder has no visible subfolders.</p>}</div>
    <footer><span className="mono">{listing?.path}</span><button onClick={onClose}>Cancel</button><button className="primary" disabled={!listing || loading} onClick={() => listing && void onChoose(listing.path)}>Use this folder</button></footer>
  </section></div>;
}

function Inspector({ selection, scan, onOpen, groups, onGroups }: { selection: Selection; scan: WorkspaceScan | null; onOpen: (path: string, line?: number) => void; groups: SavedGroup[]; onGroups: (g: SavedGroup[]) => void }) {
  if (!scan) return <p className="muted">Load an authorized ROS 2 workspace to inspect packages and relationships.</p>;
  if (!selection) return <><h2>Workspace summary</h2><div className="kv tight"><span>Path</span><span className="mono">{scan.path}</span><span>Packages</span><span>{scan.summary.packages}</span><span>Dependencies</span><span>{scan.summary.declared_dependencies}</span><span>External</span><span>{scan.summary.external_dependencies}</span><span>Launch files</span><span>{scan.summary.launch_files}</span><span>Cycles</span><span>{scan.summary.cycles.length}</span></div>{scan.summary.cycles.map((cycle, i) => <Notice key={i} kind="warn">Cycle: {cycle.join(" → ")} → {cycle[0]}</Notice>)}<h2>Visual groups</h2>{groups.map(group => <div className="group-editor" key={group.id}><button onClick={() => onGroups(groups.map(g => g.id === group.id ? { ...g, collapsed: !g.collapsed } : g))}>{group.collapsed ? "Expand" : "Collapse"}</button><input value={group.name} maxLength={80} onChange={e => onGroups(groups.map(g => g.id === group.id ? { ...g, name: e.target.value } : g))} /><button onClick={() => { if (confirm(`Delete visual group “${group.name}”? Packages and source files are not changed.`)) onGroups(groups.filter(g => g.id !== group.id)); }}><Icon name="trash" /></button></div>)}{!groups.length && <p className="muted">No custom visual groups. Create one in Workspace mode.</p>}</>;
  if (selection.type === "edge") {
    const evidence = selection.value.evidence; const match = /^(.*?)(?::(\d+))?$/.exec(evidence);
    const path = match?.[1] ?? evidence; const line = match?.[2] ? Number(match[2]) : undefined;
    const isFile = scan.packages.some(p => p.metadata_path === path || p.files.some(f => f.path === path));
    return <><h2>Relationship</h2><div className="kv tight"><span>Source</span><span className="mono">{selection.value.source}</span><span>Target</span><span className="mono">{selection.value.target}</span><span>Type</span><span>{selection.value.kind}</span><span>Resolution</span><span>{selection.value.workspace ? "Workspace metadata" : selection.value.resolved ? "Observed in live ROS graph" : "External / unresolved in this workspace"}</span></div><h2>Evidence</h2>{isFile ? <button className="path-button mono" onClick={() => onOpen(path, line)}>{evidence}</button> : <p>{evidence}</p>}<p className="muted">Declared, observed, and heuristic relationships are labelled separately. An external dependency may still be installed in the ROS environment.</p></>;
  }
  if (selection.type === "runtime") return <><h2>Runtime component</h2><p className="mono">{selection.id}</p><Notice>Runtime-to-package association is heuristic unless launch metadata provides an exact package and executable match.</Notice></>;
  const pkg = selection.type === "file" ? selection.package : selection.value;
  return <><h2>Package</h2><div className="kv tight"><span>Name</span><span className="mono">{pkg.name}</span><span>Path</span><span className="mono">{pkg.path}</span><span>Build system</span><span>{pkg.build_type}</span><span>Version</span><span>{pkg.version ?? "not declared"}</span><span>Executables</span><span>{pkg.executables.join(", ") || "none discovered"}</span></div>{pkg.description && <p>{pkg.description}</p>}
    {pkg.warnings.map(x => <Notice key={x} kind="warn">{x}</Notice>)}
    <h2>Dependencies ({pkg.dependencies.length})</h2><div className="chip-list">{pkg.dependencies.map(d => <span key={d.kind + d.name}>{d.name}<small>{d.kind}</small></span>)}</div>
    <h2>Reverse dependencies ({pkg.reverse_dependencies.length})</h2><div className="chip-list">{pkg.reverse_dependencies.map(x => <span key={x}>{x}</span>)}</div>
    <h2>Visual group</h2><select value={groups.find(g => g.members.includes(pkg.name))?.id ?? ""} onChange={e => { const next = groups.map(g => ({ ...g, members: g.members.filter(x => x !== pkg.name) })); if (e.target.value) next.find(g => g.id === e.target.value)!.members.push(pkg.name); onGroups(next); }}><option value="">Ungrouped</option>{groups.map(g => <option key={g.id} value={g.id}>{g.name}</option>)}</select>
    <h2>Files</h2><div className="inspector-files">{pkg.files.map(f => <button key={f.path} className="path-button mono" onClick={() => onOpen(f.path)}>{f.path}</button>)}</div>
    {selection.type === "file" && <Notice>Selected file: <button className="path-button mono" onClick={() => onOpen(selection.value.path)}>{selection.value.path}</button></Notice>}</>;
}

function ExplorerCanvas({ scan, mode, search, setSelection, saved, groups, runtimeDetails, onDirty }: { scan: WorkspaceScan; mode: GraphMode; search: string; selection: Selection; setSelection: (s: Selection) => void; saved: PackageLayout | null; groups: SavedGroup[]; runtimeDetails: NodeDetail[]; onDirty: () => void }) {
  const live = useLive(); const flow = useReactFlow(); const box = useRef<HTMLDivElement>(null);
  const layoutKey = useRef(""); const viewportKey = useRef("");
  const [direction, setDirection] = useState<"LR" | "TB">("LR");
  const [showExternal, setShowExternal] = useState(scan.packages.length < 100); const [showLabels, setShowLabels] = useState(false);
  const [connected, setConnected] = useState<Set<string>>(new Set());

  const model = useMemo(() => {
    const nodes: Node<PackageNodeData>[] = []; const edges: Edge[] = [];
    const positions = saved?.mode === mode ? saved.positions : {};
    const pos = (id: string, index: number) => positions[id] ?? { x: 80 + (index % 4) * 250, y: 70 + Math.floor(index / 4) * 120 };
    if (mode === "dependencies" || mode === "architecture") {
      const collapsedMembers = mode === "architecture" ? new Set(groups.filter(g => g.collapsed).flatMap(g => g.members)) : new Set<string>();
      const visible = new Set(scan.packages.map(p => p.name));
      scan.packages.filter(p => !collapsedMembers.has(p.name)).forEach((p, i) => nodes.push({ id: p.name, type: "packageNode", position: pos(p.name, i), data: { label: p.name, subtitle: p.build_type, kind: "package", buildType: p.build_type, warning: p.warnings.length > 0 } }));
      if (showExternal && mode === "dependencies") scan.external_dependencies.forEach((name, i) => { visible.add(name); nodes.push({ id: name, type: "packageNode", position: pos(name, i + scan.packages.length), data: { label: name, subtitle: "external dependency", kind: "external" } }); });
      scan.edges.filter(e => visible.has(e.target) && !collapsedMembers.has(e.source) && !collapsedMembers.has(e.target)).forEach(e => edges.push({ id: e.id, source: e.source, target: e.target, type: "relationship", label: showLabels ? e.kind.replace("_depend", "") : undefined, markerEnd: { type: MarkerType.ArrowClosed }, data: { ...e }, style: { stroke: e.workspace ? "#607C91" : "#4A5966", strokeDasharray: e.workspace ? undefined : "5 4" } }));
      if (mode === "architecture") {
        groups.forEach((group, i) => {
          nodes.push({ id: `group:${group.id}`, type: "packageNode", position: pos(`group:${group.id}`, nodes.length + i), data: { label: group.name, subtitle: `${group.members.length} packages`, kind: "group" }, style: { zIndex: -1 } });
          if (!group.collapsed) group.members.forEach(member => edges.push({ id: `member:${group.id}:${member}`, source: `group:${group.id}`, target: member, type: "relationship", style: { stroke: group.color ?? "#53697A", strokeDasharray: "2 5" } }));
        });
      }
    } else if (mode === "launch") {
      let index = 0;
      scan.packages.forEach(pkg => pkg.launch.forEach(launch => {
        const lid = `launch:${launch.path}`; nodes.push({ id: lid, type: "packageNode", position: pos(lid, index++), data: { label: launch.path.split("/").pop()!, subtitle: pkg.name, kind: "launch", warning: launch.warnings.length > 0 } });
        launch.nodes.forEach((n, j) => { const nid = `declared:${launch.path}:${j}`; nodes.push({ id: nid, type: "packageNode", position: pos(nid, index++), data: { label: n.name || n.executable || "dynamic node", subtitle: n.package || "package unresolved", kind: "runtime", warning: Boolean(n.dynamic) } }); edges.push({ id: `decl:${nid}`, source: lid, target: nid, type: "relationship", label: showLabels ? "declares" : undefined, markerEnd: { type: MarkerType.ArrowClosed }, data: { source: launch.path, target: n.name || n.executable || "dynamic node", kind: "launch declaration", workspace: true, resolved: !n.dynamic, evidence: `${launch.path}${n.line ? `:${n.line}` : ""}` } }); });
      }));
    } else {
      const graph = live.graph.data;
      graph?.nodes.filter(n => !n.self).forEach((n, i) => nodes.push({ id: `runtime:${n.full}`, type: "packageNode", position: pos(`runtime:${n.full}`, i), data: { label: n.name, subtitle: n.namespace, kind: "runtime", state: mode === "comparison" ? "runtime-only" : undefined } }));
      graph?.topics.forEach((t, i) => nodes.push({ id: `topic:${t.name}`, type: "packageNode", position: pos(`topic:${t.name}`, i + (graph?.nodes.length ?? 0)), data: { label: t.name, subtitle: t.types.join(", "), kind: "topic" } }));
      graph?.services.forEach((s, i) => nodes.push({ id: `service:${s.name}`, type: "packageNode", position: pos(`service:${s.name}`, nodes.length + i), data: { label: s.name, subtitle: s.types.join(", "), kind: "topic" } }));
      graph?.actions.forEach((a, i) => nodes.push({ id: `action:${a.name}`, type: "packageNode", position: pos(`action:${a.name}`, nodes.length + i), data: { label: a.name, subtitle: `action · ${a.types.join(", ")}`, kind: "topic" } }));
      const relation = (source: string, target: string, kind: string, evidence: string) => edges.push({ id: `${kind}:${source}:${target}`, source, target, type: "relationship", label: showLabels ? kind : undefined, markerEnd: { type: MarkerType.ArrowClosed }, data: { source, target, kind, workspace: false, resolved: true, evidence }, style: { stroke: kind === "publishes" ? "#49B6E8" : kind === "subscribes" ? "#34C995" : "#B58CFF" } });
      runtimeDetails.forEach(detail => {
        const nid = `runtime:${detail.name}`;
        detail.publishers.forEach(x => relation(nid, `topic:${x.name}`, "publishes", `Live ROS graph: ${detail.name} publisher endpoint`));
        detail.subscribers.forEach(x => relation(`topic:${x.name}`, nid, "subscribes", `Live ROS graph: ${detail.name} subscriber endpoint`));
        detail.service_servers.forEach(x => relation(nid, `service:${x.name}`, "serves", `Live ROS graph: ${detail.name} service server`));
        detail.service_clients.forEach(x => relation(`service:${x.name}`, nid, "calls", `Live ROS graph: ${detail.name} service client`));
      });
      if (mode === "comparison") scan.packages.forEach(pkg => pkg.launch.flatMap(x => x.nodes).forEach((n, i) => { const id = `static:${pkg.name}:${n.name || n.executable}:${i}`; const runtime = graph?.nodes.find(r => r.name === n.name || r.name === n.executable); nodes.push({ id, type: "packageNode", position: pos(id, nodes.length), data: { label: n.name || n.executable || "dynamic declaration", subtitle: pkg.name, kind: "runtime", state: runtime ? "matched" : "static-only", warning: Boolean(n.dynamic) } }); if (runtime) edges.push({ id: `match:${id}`, source: id, target: `runtime:${runtime.full}`, type: "relationship", label: "name match", markerEnd: { type: MarkerType.ArrowClosed }, style: { stroke: "#34C995", strokeDasharray: "4 3" }, data: { source: `${pkg.name}:${n.name || n.executable}`, target: runtime.full, kind: "heuristic name match", workspace: true, resolved: false, evidence: "Heuristic name/executable equality; not a confirmed source mapping" } }); }));
    }
    return { nodes, edges };
  }, [scan, mode, saved, showExternal, showLabels, groups, live.graph.data, runtimeDetails]);
  const [nodes, setNodes, onNodesChange] = useNodesState(model.nodes); const [edges, setEdges, onEdgesChange] = useEdgesState(model.edges);
  useEffect(() => {
    const key = `${scan.workspace_id}:${mode}`; const enteringMode = layoutKey.current !== key;
    setNodes(current => {
      const currentPositions = new Map(current.map(node => [node.id, node.position]));
      const next = model.nodes.map(node => ({ ...node, position: enteringMode ? node.position : currentPositions.get(node.id) ?? node.position }));
      return enteringMode && saved?.mode !== mode ? autoLayout(next, model.edges, direction) : next;
    });
    setEdges(model.edges); layoutKey.current = key;
    if (viewportKey.current !== key) {
      viewportKey.current = key;
      requestAnimationFrame(() => saved?.mode === mode && saved.viewport?.zoom
        ? flow.setViewport({ x: saved.viewport.x ?? 0, y: saved.viewport.y ?? 0, zoom: saved.viewport.zoom }, { duration: 250 })
        : flow.fitView({ padding: .18, duration: 300 }));
    }
  }, [model, mode, scan.workspace_id, setNodes, setEdges, flow, saved, direction]);
  useEffect(() => { if (!search.trim()) return; const match = nodes.find(n => String((n.data as PackageNodeData).label).toLowerCase().includes(search.toLowerCase())); if (match) { flow.setCenter(match.position.x + 95, match.position.y + 29, { zoom: 1.25, duration: 450 }); setNodes(all => all.map(n => ({ ...n, selected: n.id === match.id }))); } }, [search]); // focusing should run once per query, not after its own node-state update
  useEffect(() => { setNodes(all => all.map(node => ({ ...node, data: { ...node.data, dimmed: connected.size > 0 && !connected.has(node.id) } }))); }, [connected, setNodes]);
  const selectionChanged = useCallback(({ nodes: ns, edges: es }: OnSelectionChangeParams) => {
    if (es[0]?.data && "source" in es[0].data) setSelection({ type: "edge", value: es[0].data as unknown as DependencyEdge });
    else if (ns[0]) { const pkg = scan.packages.find(p => p.name === ns[0].id); setSelection(pkg ? { type: "package", value: pkg } : { type: "runtime", id: String((ns[0].data as PackageNodeData).label) }); }
    else setSelection(null);
    const ids = new Set<string>(); ns.forEach(n => { ids.add(n.id); edges.forEach(e => { if (e.source === n.id) ids.add(e.target); if (e.target === n.id) ids.add(e.source); }); }); setConnected(ids);
  }, [edges, scan.packages, setSelection]);
  const reset = () => { if (!confirm("Restore automatic layout and discard unsaved node positions?")) return; setNodes(n => autoLayout(n, edges, direction)); onDirty(); requestAnimationFrame(() => flow.fitView({ padding: .15, duration: 400 })); };
  const exportGraph = async (format: "png" | "svg") => { if (!box.current) return; const options = { backgroundColor: "#11161D", pixelRatio: 2, filter: (node: HTMLElement) => !node.classList?.contains("react-flow__controls") && !node.classList?.contains("react-flow__minimap") }; const url = format === "png" ? await toPng(box.current, options) : await toSvg(box.current, options); download(url, `${slug(scan.name)}-${mode}.${format}`); };
  return <div className="package-canvas" ref={box}><ReactFlow nodes={nodes} edges={edges} nodeTypes={NODE_TYPES} edgeTypes={EDGE_TYPES} onNodesChange={changes => { onNodesChange(changes); if (changes.some(c => c.type === "position" && c.dragging)) onDirty(); }} onEdgesChange={onEdgesChange} onSelectionChange={selectionChanged} onNodeDoubleClick={(_, n) => flow.fitView({ nodes: [n], padding: .7, duration: 400 })} onPaneClick={() => { setSelection(null); setConnected(new Set()); }} selectionOnDrag panOnDrag={[1, 2]} selectionMode={SelectionMode.Partial} multiSelectionKeyCode={["Control", "Meta"]} minZoom={.08} maxZoom={2.5} onlyRenderVisibleElements fitView>
    <Background variant={BackgroundVariant.Dots} gap={18} size={1} color="#3A4650" /><MiniMap pannable zoomable nodeColor={n => COLORS[(n.data as PackageNodeData).buildType ?? (n.data as PackageNodeData).kind] ?? "#607C91"} maskColor="rgba(7,10,14,.72)" /><Controls showInteractive={false} />
    <Panel position="top-left" className="canvas-panel"><label><input type="checkbox" checked={showLabels} onChange={e => setShowLabels(e.target.checked)} /> Edge labels</label>{mode === "dependencies" && <label><input type="checkbox" checked={showExternal} onChange={e => setShowExternal(e.target.checked)} /> External</label>}<button onClick={() => { setDirection(d => d === "LR" ? "TB" : "LR"); setNodes(n => autoLayout(n, edges, direction === "LR" ? "TB" : "LR")); onDirty(); }}>{direction}</button><button onClick={reset}><Icon name="refresh" />Auto layout</button></Panel>
    <Panel position="top-right" className="canvas-panel"><button onClick={() => flow.fitView({ padding: .15, duration: 350 })}>Fit</button><button onClick={() => exportGraph("png")}><Icon name="download" />PNG</button><button onClick={() => exportGraph("svg")}>SVG</button><button onClick={() => box.current?.requestFullscreen()} title="Full screen"><Icon name="expand" /></button></Panel>
  </ReactFlow></div>;
}

function Page() {
  const { graph } = useLive(); const { setDock } = useApp();
  const [path, setPath] = useState(""); const [roots, setRoots] = useState<{ path: string; available: boolean }[]>([]);
  const [scan, setScan] = useState<WorkspaceScan | null>(null); const [busy, setBusy] = useState(false); const [error, setError] = useState("");
  const [mode, setMode] = useState<GraphMode>("dependencies"); const [search, setSearch] = useState(""); const [filter, setFilter] = useState("");
  const [selection, setSelection] = useState<Selection>(null); const [source, setSource] = useState<SourceFile | null>(null); const [focusLine, setFocusLine] = useState<number>();
  const [saved, setSaved] = useState<PackageLayout | null>(null); const [groups, setGroups] = useState<SavedGroup[]>([]); const [dirty, setDirty] = useState(false); const flow = useReactFlow();
  const [runtimeDetails, setRuntimeDetails] = useState<NodeDetail[]>([]);
  const [treeCollapsed, setTreeCollapsed] = useState(false);
  const [choosingFolder, setChoosingFolder] = useState(false);
  useEffect(() => { api<{ path: string; available: boolean }[]>("/api/package-explorer/roots").then(r => { setRoots(r); const first = r.find(x => x.available); if (first) setPath(first.path); }).catch(e => setError(e.message)); }, []);
  useEffect(() => {
    let active = true;
    if ((mode !== "live" && mode !== "comparison") || !graph.data) { setRuntimeDetails([]); return; }
    const visible = graph.data.nodes.filter(n => !n.self).slice(0, 250);
    Promise.all(visible.map(n => api<NodeDetail>(`/api/live/node?name=${encodeURIComponent(n.full)}`).catch(() => null)))
      .then(rows => { if (active) setRuntimeDetails(rows.filter((x): x is NodeDetail => x !== null)); });
    return () => { active = false; };
  }, [mode, graph.updated]);
  const openFile = useCallback(async (filePath: string, line?: number) => { if (!scan) return; try { setSource(await api<SourceFile>(`/api/package-explorer/file?workspace=${encodeURIComponent(scan.path)}&path=${encodeURIComponent(filePath)}`)); setFocusLine(line); } catch (e) { setError(e instanceof Error ? e.message : String(e)); } }, [scan]);
  useDock(<Inspector selection={selection} scan={scan} onOpen={openFile} groups={groups} onGroups={g => { setGroups(g); setDirty(true); }} />, [selection, scan, groups]);
  async function load(target = path) { setBusy(true); setError(""); setSource(null); try { const next = await api<WorkspaceScan>("/api/package-explorer/scan", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ path: target }) }); setScan(next); setSelection(null); const layout = await api<PackageLayout | null>(`/api/package-explorer/layouts/${next.workspace_id}`); setSaved(layout); setMode(layout?.mode ?? "dependencies"); setGroups(layout?.groups ?? []); setDirty(false); } catch (e) { setError(e instanceof Error ? e.message : String(e)); } finally { setBusy(false); } }
  async function chooseFolder(selected: string) { setBusy(true); setError(""); try { const added = await api<{ path: string; available: boolean; packages: number }>("/api/package-explorer/roots", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ path: selected }) }); setRoots(current => [...current.filter(root => root.path !== added.path), added]); setPath(added.path); setChoosingFolder(false); await load(added.path); } catch (e) { setError(e instanceof Error ? e.message : String(e)); setBusy(false); } }
  async function save() { if (!scan) return; const positions = Object.fromEntries(flow.getNodes().map(n => [n.id, n.position])); const viewport = flow.getViewport(); const layout: PackageLayout = { workspace_id: scan.workspace_id, mode, positions, viewport, groups }; try { await api(`/api/package-explorer/layouts/${scan.workspace_id}`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(layout) }); setSaved(layout); setDirty(false); } catch (e) { setError(e instanceof Error ? e.message : String(e)); } }
  const packages = scan?.packages.filter(p => `${p.name} ${p.path} ${p.build_type}`.toLowerCase().includes(filter.toLowerCase())) ?? [];
  return <div className="page package-page"><div className="package-title"><div><h1>ROS 2 Package Explorer</h1><p className="sub">Static workspace architecture and the connected ROS graph. Source analysis is read only.</p></div>{scan && <><span className="workspace-id mono">{scan.name} · {scan.workspace_id}</span><button disabled={!dirty} onClick={save}>{dirty ? "Save layout" : "Layout saved"}</button></>}</div>
    {error && <Notice kind="err">{error}</Notice>}<div className="workspace-loader"><select className="mono" value={path} onChange={e => setPath(e.target.value)} aria-label="Workspace"><option value="" disabled>Select a workspace</option>{roots.filter(x => x.available).map(x => <option key={x.path} value={x.path}>{x.path}</option>)}</select><button onClick={() => setChoosingFolder(true)}><Icon name="folder" />Add workspace</button><button disabled={busy || !path} onClick={() => void load()}><Icon name="refresh" />{busy ? "Scanning…" : scan ? "Rescan" : "Open workspace"}</button></div>
    {choosingFolder && <FolderBrowser onClose={() => setChoosingFolder(false)} onChoose={chooseFolder} />}
    {!scan && !busy && <Empty title="Load a ROS 2 workspace">Enter a directory under an authorized workspace root. The backend finds package.xml files without requiring a build or a live robot.</Empty>}
    {scan && <><div className="package-summary"><Tile label="Packages" value={scan.summary.packages} /><Tile label="Dependencies" value={scan.summary.declared_dependencies} /><Tile label="External" value={scan.summary.external_dependencies} tone={scan.summary.external_dependencies ? "warn" : undefined} /><Tile label="Launch files" value={scan.summary.launch_files} /><Tile label="Cycles" value={scan.summary.cycles.length} tone={scan.summary.cycles.length ? "warn" : undefined} /></div>
      <div className="package-modebar">{(Object.keys(MODE_LABELS) as GraphMode[]).map(x => <button key={x} aria-pressed={mode === x} onClick={() => { setMode(x); setDirty(true); }}>{MODE_LABELS[x]}</button>)}<span className="spacer" /><input type="search" placeholder="Find and focus component…" value={search} onChange={e => setSearch(e.target.value)} />{mode === "architecture" && <button onClick={() => { const name = prompt("Group name"); if (name?.trim()) { setGroups([...groups, { id: crypto.randomUUID(), name: name.trim().slice(0, 80), members: [], collapsed: false }]); setDirty(true); } }}><Icon name="plus" />New group</button>}</div>
      {(mode === "live" || mode === "comparison") && !graph.data && <Notice kind="warn">The ROS agent is disconnected or discovery is unavailable. Static workspace data remains usable; live components will appear after connection.</Notice>}
      <div className={`package-workspace ${treeCollapsed ? "tree-collapsed" : ""}`}><aside className="workspace-tree"><div className="tree-head"><strong>{treeCollapsed ? "WS" : "Workspace"}</strong>{!treeCollapsed && <span>{packages.length}/{scan.packages.length}</span>}<button title={treeCollapsed ? "Expand workspace tree" : "Collapse workspace tree"} onClick={() => setTreeCollapsed(x => !x)}><Icon name={treeCollapsed ? "right" : "left"} size={12} /></button></div>{!treeCollapsed && <><input type="search" placeholder="Filter packages and files…" value={filter} onChange={e => setFilter(e.target.value)} />
        <div className="tree-scroll">{packages.map(pkg => <TreePackage key={pkg.name} pkg={pkg} selected={selection} onPackage={() => { setSelection({ type: "package", value: pkg }); setSearch(pkg.name); }} onFile={file => { setSelection({ type: "file", package: pkg, value: file }); setSearch(pkg.name); void openFile(file.path); }} />)}</div>
        </>}</aside>
        <section className="canvas-column">{source ? <><div className="source-toolbar"><button onClick={() => setSource(null)}><Icon name="left" />Back to graph</button></div><SourceViewer file={source} focusLine={focusLine} /></> : <ExplorerCanvas scan={scan} mode={mode} search={search} selection={selection} setSelection={setSelection} saved={saved} groups={groups} runtimeDetails={runtimeDetails} onDirty={() => setDirty(true)} />}</section></div></>}
  </div>;
}

export function PackageExplorerPage() { return <ReactFlowProvider><Page /></ReactFlowProvider>; }
