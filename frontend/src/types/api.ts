// Mirrors backend/core/models.py and the agent's payloads.
export type Mode = "live" | "offline";
export interface SessionInfo {
  mode: Mode; version: string; agent_connected: boolean;
  capabilities: Record<string, boolean>; test_tools_enabled: boolean;
}
export interface RosInfo {
  available: boolean; distro: string | null; domain_id: string | null; rmw: string | null; error: string | null;
  discovery: "active" | "error" | "unavailable" | null; discovery_error: string | null;
}
export interface LiveStatus {
  mode: Mode;
  agent: { state: "connected" | "connecting" | "disconnected" | "disabled"; url: string | null; last_error: string | null; version: string | null };
  ros: RosInfo | null;
  host: { name: string; os: string; machine: string; cores: number } | null;
}
export interface QoS { reliability: string | null; durability: string | null; history: string | null; depth: number | null; liveliness?: string | null }
export interface Endpoint { node: string; namespace: string; type: string; qos: QoS }
export interface GraphNode { name: string; namespace: string; full: string; self: boolean }
export interface GraphTopic { name: string; types: string[]; publishers: number; subscribers: number }
export interface GraphIface { name: string; types: string[] }
export interface Graph { nodes: GraphNode[]; topics: GraphTopic[]; services: GraphIface[]; actions: GraphIface[]; warnings: string[] }
export interface FieldInfo { path: string; type: string; needs_index: boolean }
export interface TopicDetail {
  name: string; types: string[]; publishers: Endpoint[]; subscribers: Endpoint[];
  qos_conflicts: { publisher: string; subscriber: string; reason: string }[];
  fields: FieldInfo[]; fields_error: string | null; monitored: boolean;
}
export interface NodeDetail {
  name: string; publishers: GraphIface[]; subscribers: GraphIface[]; service_servers: GraphIface[]; service_clients: GraphIface[];
}
export interface TopicStatsData {
  window_s: number; samples_in_window: number; hz: number | null; period_ms: number | null; jitter_ms: number | null;
  bandwidth_bps: number | null; avg_hz: number | null; count: number; last_size_bytes: number | null;
  last_recv_ns: number | null; since_last_s: number | null; monitored_for_s: number;
}
export interface TopicStatsEvent {
  ch: "stats"; topic: string; stats: TopicStatsData; status: string; evidence: string;
  publishers: number; subscribers: number; error: string | null; types: string[];
}
export interface SampleEvent { ch: "sample"; topic: string; t_ns: number; size: number | null; values?: Record<string, number | null>; payload?: unknown }
export interface HostSample {
  ch?: "host"; t_ns: number; host: { name: string; os: string; machine: string; cores: number }; uptime_s: number;
  cpu: { percent: number | null; per_core: number[]; freq_mhz: number | null; load_avg: number[] | null };
  memory: { percent: number; used: number; total: number }; swap: { percent: number; used: number; total: number };
  disk: { path: string; percent: number; used: number; total: number; free: number } | null;
  network: { rx_bps: number | null; tx_bps: number | null };
  temperature_c: number | null; temperatures: Record<string, number>;
  gpu: { source: string; util_percent: number | null; mem_used_mib: number | null; mem_total_mib: number | null; temp_c: number | null } | null;
}
export interface AppDiag {
  backend: { pid: number; rss_bytes: number; cpu_percent: number; uptime_s: number; browser_clients: number; dropped_events: number };
  agent: { pid: number; rss_bytes: number; cpu_percent: number; threads: number; uptime_s: number; monitored_topics: number; sessions: number; dropped_events: number; decode_errors: number } | null;
}
