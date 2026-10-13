import { useCallback, useRef, useState, type ReactNode } from "react";

export function ResizableDock({ children, min = 240, max = 640, initial = 340 }: { children: ReactNode; min?: number; max?: number; initial?: number }) {
  const [w, setW] = useState(() => Number(localStorage.getItem("rds.dock")) || initial);
  const [collapsed, setCollapsed] = useState(() => localStorage.getItem("rds.dock.collapsed") === "1");
  const [drag, setDrag] = useState(false);
  const start = useRef({ x: 0, w: 0 });
  const onMove = useCallback((e: PointerEvent) => setW(Math.min(max, Math.max(min, start.current.w + (start.current.x - e.clientX)))), [min, max]);
  const onUp = useCallback(() => {
    setDrag(false); window.removeEventListener("pointermove", onMove); window.removeEventListener("pointerup", onUp);
  }, [onMove]);
  const toggle = () => { const c = !collapsed; setCollapsed(c); localStorage.setItem("rds.dock.collapsed", c ? "1" : "0"); };
  if (collapsed) return <aside className="dock collapsed"><button onClick={toggle} title="Show details" aria-label="Show details panel">«</button></aside>;
  return (<>
    <div className={"resizer" + (drag ? " drag" : "")} role="separator" aria-orientation="vertical"
      onPointerDown={e => { start.current = { x: e.clientX, w }; setDrag(true); window.addEventListener("pointermove", onMove); window.addEventListener("pointerup", onUp); }} />
    <aside className="dock" style={{ width: w }} onPointerUp={() => localStorage.setItem("rds.dock", String(w))}>
      <div className="dockhead"><h2 style={{ margin: 0 }}>Details</h2><button onClick={toggle} title="Collapse panel" aria-label="Collapse details panel">»</button></div>
      {children}
    </aside>
  </>);
}
