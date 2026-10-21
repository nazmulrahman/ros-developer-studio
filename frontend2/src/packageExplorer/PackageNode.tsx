import { Handle, Position, type NodeProps } from "@xyflow/react";
import { Icon } from "../components/Icon";

export interface PackageNodeData extends Record<string, unknown> {
  label: string; subtitle?: string; kind: "package" | "external" | "launch" | "runtime" | "topic" | "group";
  buildType?: string; warning?: boolean; state?: "matched" | "static-only" | "runtime-only" | "unknown"; dimmed?: boolean;
}

export function PackageNode({ data, selected }: NodeProps) {
  const d = data as PackageNodeData;
  return <div className={`pkg-node ${d.kind} ${selected ? "selected" : ""} ${d.dimmed ? "dimmed" : ""} ${d.state ?? ""}`}>
    <Handle type="target" position={Position.Left} />
    <div className="pkg-node-icon"><Icon name={d.kind === "launch" ? "play" : d.kind === "runtime" ? "cpu" : d.kind === "topic" ? "signals" : d.kind === "group" ? "folder" : "package"} size={14} /></div>
    <div className="pkg-node-copy"><strong>{d.label}</strong>{d.subtitle && <span>{d.subtitle}</span>}</div>
    {d.warning && <span className="pkg-warning" title="Analysis warning">!</span>}
    <Handle type="source" position={Position.Right} />
  </div>;
}
