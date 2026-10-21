import { createContext, useContext, useEffect, type ReactNode } from "react";

interface AppCtx {
  page: string; setPage: (p: string) => void;
  selectedTopic: string | null; setSelectedTopic: (t: string | null) => void;
  setDock: (n: ReactNode) => void;
}
export const AppContext = createContext<AppCtx>(null as unknown as AppCtx);
export const useApp = () => useContext(AppContext);

/** Publish context-sensitive content to the right-hand Details panel; cleared on unmount. */
export function useDock(node: ReactNode, deps: unknown[]) {
  const { setDock } = useApp();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { setDock(node); }, deps);
  useEffect(() => () => setDock(null), [setDock]);
}
