import { lazy, Suspense, useCallback, useState, type ReactNode } from "react";
import { PAGES } from "./pages/pages";
import { Sidebar } from "./components/Sidebar";
import { TopBar } from "./components/TopBar";
import { PageStub } from "./components/PageStub";
import { ResizableDock } from "./components/ResizableDock";
import { ExplorerPage } from "./pages/ExplorerPage";
import { InspectorPage } from "./pages/InspectorPage";
import { SignalsPage } from "./pages/SignalsPage";
import { HostPage } from "./pages/HostPage";
import { MotionPage } from "./pages/MotionPage";
import { VisualizationsPage } from "./pages/VisualizationsPage";
import { SettingsPage } from "./pages/SettingsPage";
import { DiagnosticsPage } from "./pages/DiagnosticsPage";
import { OverviewPage } from "./pages/OverviewPage";
import { AppContext } from "./services/app";
import { LiveProvider, useLive } from "./services/live";
import { api, getToken, setToken } from "./services/api";
import type { Mode } from "./types/api";

const PackageExplorerPage = lazy(() => import("./pages/PackageExplorerPage").then(x => ({ default: x.PackageExplorerPage })));
const BagStudioPage = lazy(() => import("./pages/BagStudioPage").then(x => ({ default: x.BagStudioPage })));

function Shell({ token, onToken }: { token: string; onToken: (t: string) => void }) {
  const { status, wsState, bag, cursor, seek, playing, setPlaying, rate, setRate } = useLive();
  const [page, setPage] = useState("overview");
  const [collapsed, setCollapsed] = useState(false);
  const [selectedTopic, setSelectedTopic] = useState<string | null>(null);
  const [dock, setDockNode] = useState<ReactNode>(null);
  const setDock = useCallback((n: ReactNode) => setDockNode(n), []);
  const mode: Mode = status?.mode ?? "live";
  const def = PAGES.find(p => p.id === page)!;
  const view = !def.ready ? <PageStub page={def} /> : page === "overview" ? <OverviewPage /> : page === "explorer" ? <ExplorerPage /> : page === "packages" ? <Suspense fallback={<div className="page"><p>Loading Package Explorer…</p></div>}><PackageExplorerPage /></Suspense>
    : page === "diagnostics" ? <DiagnosticsPage /> : page === "bags" ? <Suspense fallback={<div className="page"><p>Loading Bag Studio…</p></div>}><BagStudioPage /></Suspense> : page === "motion" ? <MotionPage /> : page === "viz" ? <VisualizationsPage /> : page === "settings" ? <SettingsPage /> : page === "inspector" ? <InspectorPage /> : page === "signals" ? <SignalsPage /> : <HostPage />;
  return (
    <AppContext.Provider value={{ page, setPage, selectedTopic, setSelectedTopic, setDock }}>
      <div className="shell">
        <Sidebar page={page} onPage={setPage} collapsed={collapsed} onToggle={() => setCollapsed(c => !c)} host={status?.host?.name} agentOk={status?.agent.state === "connected"} />
        <div className="stage">
          <TopBar mode={mode} onMode={m => { api("/api/session/mode", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ mode: m }) }).catch(() => {}); }}
            wsState={wsState} status={status} token={token} onToken={onToken} />
        {mode === "offline" && bag && <div className="record-bar"><strong>Recording source</strong><span>{bag.path.split("/").pop()}</span><button onClick={()=>setPlaying(!playing)}>{playing ? "Pause" : "Play"}</button><select value={rate} onChange={e=>setRate(Number(e.target.value))}>{[.25,.5,1,2,4].map(v=><option key={v} value={v}>{v}×</option>)}</select><input aria-label="Shared recording timeline" type="range" min={bag.start_ns} max={bag.start_ns+bag.duration_ns} value={cursor} onChange={e=>seek(Number(e.target.value))}/><span>{((cursor-bag.start_ns)/1e9).toFixed(2)} s</span></div>}
          <main className="main">{view}
            <ResizableDock>{dock ?? <p className="muted">Nothing selected.</p>}</ResizableDock></main>
        </div>
      </div>
    </AppContext.Provider>);
}

export default function App() {
  const [token, setTok] = useState(getToken());
  return <LiveProvider token={token}><Shell token={token} onToken={t => { setToken(t); setTok(t); }} /></LiveProvider>;
}
