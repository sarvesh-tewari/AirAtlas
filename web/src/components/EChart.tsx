// Thin ECharts wrapper: inits on mount, re-applies option on change, auto-resizes.

import { useEffect, useRef } from "react";
import * as echarts from "echarts";

export function EChart({ option, height = 280, ariaLabel }: { option: echarts.EChartsCoreOption; height?: number; ariaLabel?: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const chartRef = useRef<echarts.ECharts | null>(null);

  // Initialise once; dispose on unmount.
  useEffect(() => {
    if (!ref.current) return;
    const chart = echarts.init(ref.current, undefined, { renderer: "canvas" });
    chartRef.current = chart;
    const ro = new ResizeObserver(() => chart.resize());
    ro.observe(ref.current);
    return () => {
      ro.disconnect();
      chart.dispose();
      chartRef.current = null;
    };
  }, []);

  // Update on option change (no dispose/re-init - avoids flash + ResizeObserver churn).
  useEffect(() => {
    chartRef.current?.setOption({ aria: { enabled: true }, ...option }, true);
  }, [option]);

  return <div ref={ref} role="img" aria-label={ariaLabel} style={{ height, width: "100%" }} />;
}
