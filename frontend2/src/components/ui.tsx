import type { ReactNode } from "react";

export const Tile = ({ label, value, sub, tone }: { label: string; value: ReactNode; sub?: ReactNode; tone?: "ok" | "warn" | "err" }) => (
  <div className={"tile" + (tone ? " " + tone : "")}><div className="lbl">{label}</div><div className="val mono">{value}</div>{sub && <div className="sub muted">{sub}</div>}</div>);

export const Notice = ({ kind = "info", children }: { kind?: "info" | "warn" | "err"; children: ReactNode }) => <div className={"notice " + kind}>{children}</div>;
export const Empty = ({ title, children }: { title: string; children?: ReactNode }) => <div className="emptybox"><strong>{title}</strong>{children && <div className="muted">{children}</div>}</div>;

const TONE: Record<string, "ok" | "warn" | "err" | ""> = { receiving: "ok", stalled: "warn", publisher_no_data: "warn", no_publisher: "err", topic_missing: "err", unknown: "" };
const TEXT: Record<string, string> = { receiving: "Active", stalled: "Stalled", publisher_no_data: "No messages received", no_publisher: "No publisher", topic_missing: "Topic gone", unknown: "Unknown" };
export const StatusBadge = ({ status }: { status: string }) => <span className={"status " + (TONE[status] ?? "")}>{TEXT[status] ?? status}</span>;
