import dagre from "@dagrejs/dagre";
import type { Edge, Node } from "@xyflow/react";

export function autoLayout<T extends Record<string, unknown>>(nodes: Node<T>[], edges: Edge[], direction: "LR" | "TB" = "LR"): Node<T>[] {
  const graph = new dagre.graphlib.Graph().setDefaultEdgeLabel(() => ({}));
  graph.setGraph({ rankdir: direction, nodesep: 42, ranksep: 100, marginx: 40, marginy: 40 });
  nodes.forEach(node => graph.setNode(node.id, { width: node.type === "group" ? 360 : 190, height: node.type === "group" ? 240 : 58 }));
  edges.forEach(edge => { if (graph.hasNode(edge.source) && graph.hasNode(edge.target)) graph.setEdge(edge.source, edge.target); });
  dagre.layout(graph);
  return nodes.map(node => { const p = graph.node(node.id); return { ...node, position: { x: p.x - (node.type === "group" ? 180 : 95), y: p.y - (node.type === "group" ? 120 : 29) } }; });
}
