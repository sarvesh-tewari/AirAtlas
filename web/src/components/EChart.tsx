// Thin ECharts wrapper: inits on mount, re-applies option on change, auto-resizes.

import { useEffect, useRef } from "react";
import * as echarts from "echarts";

export function EChart({ option, height = 280 }: { option: echarts.EChartsCoreOption; height?: number }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!ref.current) return;
    const chart = echarts.init(ref.current, undefined, { renderer: "canvas" });
    chart.setOption(option);
    const ro = new ResizeObserver(() => chart.resize());
    ro.observe(ref.current);
    return () => {
      ro.disconnect();
      chart.dispose();
    };
  }, [option]);
  return <div ref={ref} style={{ height, width: "100%" }} />;
}

// Theme-aware chart colors (canvas can't read CSS vars).
export function chartTheme(dark: boolean) {
  return {
    label: dark ? "#9aa0aa" : "#6a6e76",
    axis: dark ? "rgba(255,255,255,0.12)" : "rgba(20,22,28,0.12)",
    split: dark ? "rgba(255,255,255,0.06)" : "rgba(20,22,28,0.06)",
    ink: dark ? "#e8eaed" : "#17181b",
    accent: dark ? "#7aa5dc" : "#24426b",
    tooltipBg: dark ? "#20242b" : "#ffffff",
  };
}
