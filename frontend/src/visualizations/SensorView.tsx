import { useEffect, useState } from "react";
import { Empty, Notice, Tile } from "../components/ui";
import { finite, orientation, type NormalizedSample } from "./model";
const number = (v: unknown, digits = 3) => finite(v)?.toFixed(digits) ?? "—";
const array = (v: unknown): any[] => Array.isArray(v) ? v : v && typeof v === "object" && "items" in v && Array.isArray(v.items) ? v.items : [];
function XY({ points, path = false }: { points: number[][]; path?: boolean }) {
  const valid = points.filter(p => p.length >= 2 && finite(p[0]) !== null && finite(p[1]) !== null);
  const xs = valid.map(p => p[0]), ys = valid.map(p => p[1]);
  const minX = Math.min(0, ...xs), maxX = Math.max(0, ...xs), minY = Math.min(0, ...ys), maxY = Math.max(0, ...ys);
  const span = Math.max(1, maxX - minX, maxY - minY) * 1.15;
  const cx = (minX + maxX) / 2, cy = (minY + maxY) / 2;
  const convert = ([x, y]: number[]) => [160 + (x - cx) * 290 / span, 160 - (y - cy) * 290 / span];
  const origin = convert([0, 0]); const converted = valid.map(convert);
  return <><svg className="sensor-canvas" viewBox="0 0 320 320" role="img" aria-label={path ? "Odometry XY trace in message frame" : "Laser scan in sensor frame"}>
    <path d={`M0 ${origin[1]} H320 M${origin[0]} 0 V320`} stroke="#334454" strokeWidth="1" />
    {path ? <polyline points={converted.map(p => p.join(",")).join(" ")} fill="none" stroke="#49B6E8" strokeWidth="1.5" /> : converted.map((p, i) => <circle key={i} cx={p[0]} cy={p[1]} r="1.5" fill="#34C995" />)}
    <circle cx={origin[0]} cy={origin[1]} r="3" fill="#F5AD57" /><text x="8" y="310" fill="#93A6B7" fontSize="11">+X right · +Y up · span {span.toFixed(2)} m</text></svg>{!valid.length && <p className="muted">No valid points in this sample.</p>}</>;
}
function Vector({ label, value, unit }: { label: string; value: any; unit: string }) { return <div className="ep"><strong>{label}</strong><div className="mono">x {number(value?.x)} · y {number(value?.y)} · z {number(value?.z)} {unit}</div></div>; }
function Attitude({ quaternion, unavailable = false }: { quaternion: any; unavailable?: boolean }) {
  const angles = unavailable ? null : orientation(quaternion);
  return <><div className="tiles">{(["roll", "pitch", "yaw"] as const).map(k => <Tile key={k} label={k} value={angles ? `${number(angles[k], 1)}°` : "—"} />)}</div>
    {!angles && <p className="muted">Orientation unavailable (invalid quaternion or covariance marks it absent).</p>}
    {angles && <svg viewBox="0 0 300 100" className="attitude" role="img" aria-label="Roll and pitch indicator"><g transform={`translate(150 ${50 + Math.max(-40, Math.min(40, angles.pitch))}) rotate(${-angles.roll})`}><line x1="-80" y1="0" x2="80" y2="0" stroke="#49B6E8" strokeWidth="3" /></g><path d="M125 50 H145 M155 50 H175 M150 45 V55" stroke="#F5AD57" strokeWidth="2" /></svg>}</>;
}
function Odom({ data, sample }: { data: any; sample: NormalizedSample }) {
  const [trace, setTrace] = useState<{ frame: string; points: number[][] }>({ frame: "", points: [] });
  const frame = String(data?.header?.frame_id ?? "");
  useEffect(() => { const p = data?.pose?.pose?.position; if (finite(p?.x) !== null && finite(p?.y) !== null) setTrace(old => ({ frame, points: [...(old.frame === frame ? old.points : []), [p.x, p.y]].slice(-1000) })); }, [sample, data, frame]);
  return <><p className="muted">Frame: {frame || "unspecified"} · child: {data?.child_frame_id || "unspecified"}</p><XY points={trace.frame === frame ? trace.points : []} path /><p className="muted">Last 1,000 displayed poses, in message coordinates. No TF projection.</p><Vector label="Position" value={data?.pose?.pose?.position} unit="m" /><Attitude quaternion={data?.pose?.pose?.orientation} /><Vector label="Linear velocity" value={data?.twist?.twist?.linear} unit="m/s" /><Vector label="Angular velocity" value={data?.twist?.twist?.angular} unit="rad/s" /></>;
}
function TransformTree({ data, sample }: { data: any; sample: NormalizedSample }) {
  const [edges, setEdges] = useState<Map<string, { parent: string; child: string; stamp: string; transform: any }>>(new Map());
  useEffect(() => { setEdges(old => { const next = new Map(old); for (const tf of array(data?.transforms)) {
    const parent = tf?.header?.frame_id, child = tf?.child_frame_id;
    if (typeof parent !== "string" || typeof child !== "string" || !parent || !child) continue;
    const key = `${parent}\0${child}`; next.delete(key); next.set(key, { parent, child, stamp: `${tf.header?.stamp?.sec ?? "?"}.${String(tf.header?.stamp?.nanosec ?? 0).padStart(9, "0")}`, transform: tf.transform });
  } return new Map([...next].slice(-500)); }); }, [sample, data]);
  const rows = [...edges.values()]; const parents = new Map<string, Set<string>>(); rows.forEach(e => { if (!parents.has(e.child)) parents.set(e.child, new Set()); parents.get(e.child)!.add(e.parent); });
  return <><Notice>Observed frame relationships for this topic, up to 500 edges. Samples are rate limited; this is not a complete TF buffer or proof that a transform exists now.</Notice>
    {rows.some(e => (parents.get(e.child)?.size ?? 0) > 1) && <Notice kind="warn">Multiple observed parents for a child frame. They may have changed over time; inspect timestamps.</Notice>}
    <div className="tf-edges">{rows.map(e => <div className="ep" key={e.parent + "\0" + e.child}><div className="mono">{e.parent} → {e.child}</div><div className="muted">ROS stamp {e.stamp}</div><Vector label="Translation" value={e.transform?.translation} unit="m" /></div>)}</div>{!rows.length && <Empty title="No transforms observed" />}
    {data?.transforms?.__truncated__ && <Notice kind="warn">This message exceeds the 256-transform preview limit.</Notice>}</>;
}
export function SensorView({ sample }: { sample: NormalizedSample }) {
  const v = sample.visual; const d = v?.data;
  if (!v) return <Empty title="Waiting for a preview" />;
  if (v.error) return <Notice kind="err">{v.error}</Notice>;
  if (v.kind === "image") return <><img className="camera-preview" alt={`Camera preview from ${sample.topic}`} src={`data:image/jpeg;base64,${v.base64}`} /><p className="muted">{v.width} × {v.height} preview · original {array(v.original).join(" × ")} · frame {v.frame_id || "unspecified"}</p></>;
  if (v.kind === "scan") return <><XY points={array(v.points)} /><p className="muted">{array(v.points).length} valid points shown · stride {v.stride} of {v.total} rays · frame {v.frame_id || "unspecified"}</p></>;
  if (sample.type.endsWith("/Imu")) return <><Attitude quaternion={d?.orientation} unavailable={d?.orientation_covariance?.[0] === -1} /><Vector label="Angular velocity" value={d?.angular_velocity_covariance?.[0] === -1 ? null : d?.angular_velocity} unit="rad/s" /><Vector label="Acceleration" value={d?.linear_acceleration_covariance?.[0] === -1 ? null : d?.linear_acceleration} unit="m/s²" /></>;
  if (sample.type.endsWith("/BatteryState")) {
    const percent = finite(d?.percentage); const valid = percent !== null && percent >= 0 && percent <= 1;
    return <>{d?.present === false && <Notice kind="warn">Battery reports not present.</Notice>}<div className="tiles"><Tile label="Charge" value={valid ? `${(percent * 100).toFixed(1)}%` : "—"} /><Tile label="Voltage" value={`${number(d?.voltage, 2)} V`} /><Tile label="Current" value={`${number(d?.current, 2)} A`} /><Tile label="Temperature" value={`${number(d?.temperature, 1)} °C`} /></div>{valid && <progress max="1" value={percent} aria-label="Battery charge" />}<p className="muted">Status: {({ 0: "Unknown", 1: "Charging", 2: "Discharging", 3: "Not charging", 4: "Full" } as Record<number, string>)[d?.power_supply_status] ?? "Unknown"} · values reported by the sensor.</p></>;
  }
  if (sample.type.endsWith("/Odometry")) return <Odom data={d} sample={sample} />;
  if (sample.type.endsWith("/TFMessage")) return <TransformTree data={d} sample={sample} />;
  if (sample.type.endsWith("/DiagnosticArray")) return <>{array(d?.status).map((x, i) => <Notice key={i} kind={Number(x.level) >= 2 ? "err" : Number(x.level) === 1 ? "warn" : "info"}><strong>{x.name}</strong> · {x.message}<div className="muted">Hardware: {x.hardware_id}</div>{array(x.values).map((kv, k) => <div key={k}>{kv.key}: {kv.value}</div>)}</Notice>)}{d?.status?.__truncated__ && <Notice kind="warn">Diagnostic array exceeds preview limits.</Notice>}</>;
  const twist = sample.type.endsWith("/TwistStamped") ? d?.twist : d;
  return <><Vector label="Linear velocity" value={twist?.linear} unit="m/s" /><Vector label="Angular velocity" value={twist?.angular} unit="rad/s" /></>;
}
