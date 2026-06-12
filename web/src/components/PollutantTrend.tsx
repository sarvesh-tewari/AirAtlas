import { useMemo } from "react";
import type { EChartsCoreOption } from "echarts";
import { Activity } from "lucide-react";
import { EChart, chartTheme } from "./EChart";
import { SectionTitle } from "./SectionTitle";
import { POLLUTANT_LABELS } from "../lib/standards";
import type { DailyRow } from "../lib/data";

const SERIES: { key: keyof DailyRow; color: string }[] = [
  { key: "pm25", color: "#6366f1" },
  { key: "pm10", color: "#0ea5e9" },
  { key: "no2", color: "#f59e0b" },
  { key: "so2", color: "#a855f7" },
  { key: "o3", color: "#10b981" },
];

export function PollutantTrend({ rows, dark }: { rows: DailyRow[]; dark: boolean }) {
  const t = chartTheme(dark);
  const option = useMemo(() => {
    return {
      grid: { left: 44, right: 16, top: 30, bottom: 28 },
      legend: { top: 0, textStyle: { color: t.label, fontSize: 11 }, icon: "roundRect",
        selected: { "PM2.5": true, "PM10": true, "NO₂": false, "SO₂": false, "O₃": false } },
      tooltip: { trigger: "axis", backgroundColor: t.tooltipBg, borderWidth: 0, textStyle: { color: t.ink, fontSize: 12 } },
      xAxis: { type: "time", axisLine: { lineStyle: { color: t.axis } }, axisLabel: { color: t.label, fontSize: 11 } },
      yAxis: { type: "value", name: "µg/m³", nameTextStyle: { color: t.label, fontSize: 10 },
        axisLabel: { color: t.label, fontSize: 11 }, splitLine: { lineStyle: { color: t.split } } },
      series: SERIES.map((s) => ({
        name: POLLUTANT_LABELS[s.key as string], type: "line", showSymbol: false,
        data: rows.map((r) => [r.date, r[s.key] as number | null]),
        lineStyle: { color: s.color, width: 1.5 }, itemStyle: { color: s.color }, connectNulls: false,
      })),
    } as EChartsCoreOption;
  }, [rows, t]);

  return (
    <section className="card p-5">
      <SectionTitle icon={Activity} color="#10b981">Pollutant trends</SectionTitle>
      <p className="mb-2 text-xs text-muted">Click the legend to toggle pollutants (defaults to PM2.5 vs PM10).</p>
      <EChart option={option} height={260} ariaLabel="Per-pollutant concentration trends over time" />
    </section>
  );
}
