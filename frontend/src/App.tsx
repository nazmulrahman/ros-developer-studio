import { useCallback, useState, type ReactNode } from "react";
import { PAGES } from "./pages/pages";
import { Sidebar } from "./components/Sidebar";
import { TopBar } from "./components/TopBar";
import { PageStub } from "./components/PageStub";
import { ResizableDock } from "./components/ResizableDock";
import { ExplorerPage } from "./pages/ExplorerPage";
import { InspectorPage } from "./pages/InspectorPage";
import { SignalsPage } from "./pages/SignalsPage";
import { HostPage } from "./pages/HostPage";
import { OverviewPage } from "./pages/OverviewPage";
import { AppContext } from "./services/app";
import { LiveProvider, useLive } from "./services/live";
import { api, getToken, setToken } from "./services/api";
import type { Mode } from "./types/api";

function Shell({ token, onToken }: { token: string; onToken: (t: string) => void }) {
  const { status, wsState } = useLive();
  const [page, setPage] = useState("overview");
  const [collapsed, setCollapsed] = useState(false);
  const [selectedTopic, setSelectedTopic] = useState<string | null>(null);
  const [dock, setDockNode] = useState<ReactNode>(null);
  const setDock = useCallback((n: ReactNode) => setDockNode(n), []);
  const mode: Mode = status?.mode ?? "live";
  const def = PAGES.find(p => p.id === page)!;
  const view = !def.ready ? <PageStub page={def} /> : page === "overview" ? <OverviewPage /> : page === "explorer" ? <ExplorerPage />
    : page === "inspector" ? <InspectorPage /> : page === "signals" ? <SignalsPage /> : <HostPage />;
  return (
    <AppContext.Provider value={{ page, setPage, selectedTopic, setSelectedTopic, setDock }}>
      <div className="shell">
        <TopBar mode={mode} onMode={m => { api("/api/session/mode", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ mode: m }) }).catch(() => {}); }}
          wsState={wsState} status={status} token={token} onToken={onToken} />
        <div className="body">
          <Sidebar page={page} onPage={setPage} collapsed={collapsed} onToggle={() => setCollapsed(c => !c)} />
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
