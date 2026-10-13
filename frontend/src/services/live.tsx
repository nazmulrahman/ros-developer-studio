import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { api } from "./api";
import type { Graph, LiveStatus } from "../types/api";

export type WsState = "idle" | "connecting" | "open" | "closed" | "unauthorized";
export interface WatchSpec { hz: number; payload?: boolean; fields?: string[]; visual?: boolean }
export interface AppEvent { t: number; level: "info" | "warn" | "error"; text: string }
type Handler = (ev: any) => void;

interface Ctx {
  status: LiveStatus | null; wsState: WsState;
  graph: { data: Graph | null; loading: boolean; error: string | null; updated: number | null };
  refreshGraph: () => void;
  watch: (topic: string, spec: WatchSpec) => void; unwatch: (topic: string) => void;
  watchHost: (intervalS: number | null) => void;
  on: (ch: string, fn: Handler) => () => void;
  events: AppEvent[];
}
const LiveCtx = createContext<Ctx>(null as unknown as Ctx);
export const useLive = () => useContext(LiveCtx);

/** Subscribe to a server event channel for the lifetime of the component. */
export function useChannel(ch: string, fn: Handler) {
  const { on } = useLive();
  const ref = useRef(fn); ref.current = fn;
  useEffect(() => on(ch, e => ref.current(e)), [on, ch]);
}

export function LiveProvider({ token, children }: { token: string; children: ReactNode }) {
  const [status, setStatus] = useState<LiveStatus | null>(null);
  const [wsState, setWsState] = useState<WsState>("idle");
  const [graph, setGraph] = useState<Ctx["graph"]>({ data: null, loading: false, error: null, updated: null });
  const [events, setEvents] = useState<AppEvent[]>([]);
  const wsRef = useRef<WebSocket | null>(null);
  const watches = useRef(new Map<string, WatchSpec>());
  const hostIv = useRef<number | null>(null);
  const handlers = useRef(new Map<string, Set<Handler>>());
  const prevAgent = useRef<string | null>(null);
  const debounce = useRef<number | undefined>(undefined);

  const log = useCallback((level: AppEvent["level"], text: string) =>
    setEvents(e => [{ t: Date.now(), level, text }, ...e].slice(0, 100)), []);
  const send = useCallback((m: object) => { const ws = wsRef.current; if (ws && ws.readyState === 1) ws.send(JSON.stringify(m)); }, []);
  const on = useCallback((ch: string, fn: Handler) => {
    let s = handlers.current.get(ch); if (!s) handlers.current.set(ch, (s = new Set())); s.add(fn);
    return () => { s!.delete(fn); };
  }, []);

  const refreshGraph = useCallback(() => {
    setGraph(g => ({ ...g, loading: true }));
    api<Graph>("/api/live/graph")
      .then(d => setGraph({ data: d, loading: false, error: null, updated: Date.now() }))
      .catch(e => setGraph(g => ({ ...g, loading: false, error: e instanceof Error ? e.message : String(e) })));
  }, []);

  useEffect(() => {
    if (!token) { setWsState("idle"); setStatus(null); return; }
    let stop = false, timer: number | undefined, backoff = 500;
    const connect = () => {
      setWsState("connecting");
      const ws = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws/live?token=${encodeURIComponent(token)}`);
      wsRef.current = ws;
      ws.onopen = () => {
        backoff = 500; setWsState("open");
        watches.current.forEach((s, topic) => ws.send(JSON.stringify({ op: "watch", topic, ...s })));
        if (hostIv.current) ws.send(JSON.stringify({ op: "host", interval_s: hostIv.current }));
      };
      ws.onmessage = e => {
        const ev = JSON.parse(e.data);
        if (ev.ch === "status") setStatus(ev);
        if (ev.ch === "watch_error") log("error", `${ev.topic}: ${ev.message}`);
        if (ev.ch === "host_error") log("warn", `Host metrics: ${ev.error}`);
        handlers.current.get(ev.ch)?.forEach(h => h(ev));
      };
      ws.onclose = ev => {
        if (stop) return;
        setStatus(null);
        if (ev.code === 1008) { setWsState("unauthorized"); return; }
        setWsState("closed"); timer = window.setTimeout(connect, backoff); backoff = Math.min(backoff * 2, 5000);
      };
    };
    connect();
    return () => { stop = true; clearTimeout(timer); wsRef.current?.close(); };
  }, [token, log]);

  // agent / ROS state transitions -> event log
  useEffect(() => {
    const key = status ? `${status.agent.state}|${status.ros?.discovery ?? ""}` : null;
    if (key === prevAgent.current) return;
    if (status && prevAgent.current !== null) {
      if (status.agent.state === "connected") log("info", `Agent connected${status.ros ? ` (ROS ${status.ros.available ? status.ros.distro ?? "?" : "unavailable"})` : ""}`);
      else log("warn", `Agent ${status.agent.state}${status.agent.last_error ? `: ${status.agent.last_error}` : ""}`);
      if (status.ros?.discovery === "error") log("error", `ROS discovery error: ${status.ros.discovery_error}`);
    }
    prevAgent.current = key;
  }, [status, log]);

  const live = status?.mode === "live" && status.agent.state === "connected" && status.ros?.available === true;
  useEffect(() => { if (live) refreshGraph(); else setGraph({ data: null, loading: false, error: null, updated: null }); }, [live, refreshGraph]);
  useEffect(() => on("graph", () => {
    clearTimeout(debounce.current); debounce.current = window.setTimeout(() => { if (live) refreshGraph(); }, 300);
  }), [on, live, refreshGraph]);

  const watch = useCallback((topic: string, spec: WatchSpec) => { watches.current.set(topic, spec); send({ op: "watch", topic, ...spec }); }, [send]);
  const unwatch = useCallback((topic: string) => { if (watches.current.delete(topic)) send({ op: "unwatch", topic }); }, [send]);
  const watchHost = useCallback((iv: number | null) => { hostIv.current = iv; send({ op: "host", interval_s: iv }); }, [send]);

  return <LiveCtx.Provider value={{ status, wsState, graph, refreshGraph, watch, unwatch, watchHost, on, events }}>{children}</LiveCtx.Provider>;
}
