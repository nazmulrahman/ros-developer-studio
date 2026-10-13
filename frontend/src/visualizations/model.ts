export interface NormalizedSample {
  source_mode: "live" | "bag"; source_id: string; topic: string; type: string;
  stamps: { header_ns: string | null; receive_ns: string | null; record_ns: string | null };
  visual?: { kind?: string; error?: string; [key: string]: any };
}
export function finite(v: unknown): number | null { return typeof v === "number" && Number.isFinite(v) ? v : null; }
export function orientation(q: any): { roll: number; pitch: number; yaw: number } | null {
  const a = [q?.x, q?.y, q?.z, q?.w]; if (a.some(v => finite(v) === null)) return null;
  const norm = Math.hypot(...a); if (norm < 1e-8) return null;
  const [x, y, z, w] = a.map(v => v / norm); const deg = 180 / Math.PI;
  return { roll: Math.atan2(2 * (w * x + y * z), 1 - 2 * (x * x + y * y)) * deg,
    pitch: Math.asin(Math.max(-1, Math.min(1, 2 * (w * y - z * x)))) * deg,
    yaw: Math.atan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z)) * deg };
}
export interface Point { t: number; value: number | null; reference: boolean }
export function appendPoint(points: Point[], point: Point, max = 1200, seconds = 60): Point[] {
  return [...points.filter(p => p.t >= point.t - seconds), point].slice(-max);
}
export function mappingList(v: unknown): v is MotionWidget[] {
  const path = /^[A-Za-z_]\w*(?:\[\d+\]|\.[A-Za-z_]\w*)*$/;
  const mapping = (x: any) => x && typeof x.topic === "string" && x.topic.startsWith("/") && typeof x.path === "string" && path.test(x.path);
  return Array.isArray(v) && v.length <= 16 && new Set(v.map(x => x?.id)).size === v.length && v.every(x => x && typeof x.id === "string" && typeof x.label === "string" && typeof x.unit === "string" && mapping(x.measured) && (x.reference === null || mapping(x.reference)));
}
export interface MotionWidget { id: string; label: string; unit: string; measured: { topic: string; path: string }; reference: { topic: string; path: string } | null }
export interface VisualWidget { id: string; topic: string; type: string }
export interface TfEdge {
  id: string; parent: string; child: string; topic: string; static: boolean; stamp_ns: string | null;
  receive_ns: string; age_s: number; stale: boolean; valid_rotation: boolean;
  transform: { translation?: Record<string, number>; rotation?: Record<string, number> };
}
export interface TfSnapshot {
  frames: string[]; edges: TfEdge[]; roots: string[]; components: string[][];
  diagnostics: { severity: "warn" | "error"; code: string; message: string }[];
  updated_ns: string; limit: number;
}
export const TF_TREE_TOPIC = "@tf-tree";
export const SUPPORTED = ["sensor_msgs/msg/Image", "sensor_msgs/msg/CompressedImage", "sensor_msgs/msg/LaserScan", "sensor_msgs/msg/Imu", "sensor_msgs/msg/BatteryState", "nav_msgs/msg/Odometry", "geometry_msgs/msg/Twist", "geometry_msgs/msg/TwistStamped", "tf2_msgs/msg/TFMessage", "diagnostic_msgs/msg/DiagnosticArray"];
export function visualList(v: unknown): v is VisualWidget[] { return Array.isArray(v) && v.length <= 8 && new Set(v.map(x => x?.topic)).size === v.length && v.every(x => x && typeof x.id === "string" && typeof x.topic === "string" && (SUPPORTED.includes(x.type) || x.type === "studio/TFFrameTree")); }
