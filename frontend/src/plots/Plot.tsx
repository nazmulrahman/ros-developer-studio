import { useEffect, useRef } from "react";
import uPlot from "uplot";
import "uplot/dist/uPlot.min.css";

export interface PlotSeries { label: string; color: string }
const AXIS = { stroke: "#93A6B7", font: "11px Inter, system-ui, sans-serif", grid: { stroke: "rgba(48,62,76,.45)", width: 1 }, ticks: { stroke: "rgba(48,62,76,.7)", width: 1, size: 4 } };

/** Thin uPlot wrapper. x values are epoch seconds. Parent changes `key` when the series set changes. */
export function Plot({ series, data, xRange, height = 260, onZoom, onReset, yLabel }: {
  series: PlotSeries[]; data: uPlot.AlignedData; xRange: [number, number] | null; height?: number;
  onZoom?: (min: number, max: number) => void; onReset?: () => void; yLabel?: string;
}) {
  const box = useRef<HTMLDivElement>(null);
  const plot = useRef<uPlot | null>(null);
  const cb = useRef({ onZoom, onReset }); cb.current = { onZoom, onReset };

  useEffect(() => {
    const el = box.current!;
    const opts: uPlot.Options = {
      width: el.clientWidth || 600, height, pxAlign: false,
      scales: { x: { time: true } },
      cursor: { drag: { x: true, y: false, setScale: false } },
      legend: { show: true },
      axes: [{ ...AXIS }, { ...AXIS, size: 56, label: yLabel }],
      series: [{}, ...series.map(s => ({ label: s.label, stroke: s.color, width: 1.5, spanGaps: true, points: { show: false } }))],
      hooks: {
        setSelect: [u => {
          if (u.select.width > 4 && cb.current.onZoom) {
            cb.current.onZoom(u.posToVal(u.select.left, "x"), u.posToVal(u.select.left + u.select.width, "x"));
          }
          u.setSelect({ left: 0, top: 0, width: 0, height: 0 }, false);
        }],
        ready: [u => u.over.addEventListener("dblclick", () => cb.current.onReset?.())],
      },
    };
    const u = new uPlot(opts, data, el);
    plot.current = u;
    const ro = new ResizeObserver(() => u.setSize({ width: el.clientWidth, height }));
    ro.observe(el);
    return () => { ro.disconnect(); u.destroy(); plot.current = null; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [series.map(s => s.label + s.color).join("|"), height]);

  useEffect(() => {
    const u = plot.current; if (!u) return;
    u.setData(data, !xRange);
    if (xRange && xRange[1] > xRange[0]) u.setScale("x", { min: xRange[0], max: xRange[1] });
  }, [data, xRange]);

  return <div ref={box} style={{ width: "100%" }} />;
}
