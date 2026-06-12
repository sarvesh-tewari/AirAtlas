import { useMemo, useState } from "react";
import type { EChartsCoreOption } from "echarts";
import { CloudSun } from "lucide-react";
import { EChart, chartTheme } from "./EChart";
import { SectionTitle } from "./SectionTitle";
import type { StandardId } from "../lib/standards";
import type { DailyRow } from "../lib/data";

type Wx = "temp_c" | "rh_pct" | "precip_mm";
const WX: { key: Wx; label: string; unit: string; color: string }[] = [
  { key: "temp_c", label: "Temperature", unit: "°C", color: "#ef4444" },
  { key: "rh_pct", label: "Humidity", unit: "%", color: "#0ea5e9" },
  { key: "precip_mm", label: "Rainfall", unit: "mm", color: "#22c55e" },
];

export function WeatherOverlay({ rows, standard, dark }: { rows: DailyRow[]; standard: StandardId; dark: boolean }) {
  const t = chartTheme(dark);
  const [wx, setWx] = useState<Wx>("temp_c");
  const recent = useMemo(() => rows.slice(-120), [rows]);
  const cur = WX.find((w) => w.key === wx)!;

  const aqiKey = standard === "us" ? "aqi_us" : "aqi_naqi"; // EU falls back to NAQI numeric for the overlay
  const option = useMemo(() => ({
    grid: { left: 44, right: 48, top: 16, bottom: 28 },
    tooltip: { trigger: "axis", backgroundColor: t.tooltipBg, borderWidth: 0, textStyle: { color: t.ink, fontSize: 12 } },
    xAxis: { type: "time", axisLine: { lineStyle: { color: t.axis } }, axisLabel: { color: t.label, fontSize: 11 } },
    yAxis: [
      { type: "value", name: "AQI", nameTextStyle: { color: t.label, fontSize: 10 }, axisLabel: { color: t.label, fontSize: 11 }, splitLine: { lineStyle: { color: t.split } } },
      { type: "value", name: cur.unit, nameTextStyle: { color: cur.color, fontSize: 10 }, position: "right", axisLabel: { color: cur.color, fontSize: 11 }, splitLine: { show: false } },
    ],
    series: [
      { name: "AQI", type: "line", showSymbol: false, data: recent.map((r) => [r.date, r[aqiKey as keyof DailyRow] as number | null]), lineStyle: { color: t.ink, width: 1.5 }, itemStyle: { color: t.ink }, connectNulls: false },
      { name: cur.label, type: "line", yAxisIndex: 1, showSymbol: false, data: recent.map((r) => [r.date, r[cur.key] as number | null]), lineStyle: { color: cur.color, width: 1.5 }, itemStyle: { color: cur.color }, connectNulls: false },
    ],
  } as EChartsCoreOption), [recent, aqiKey, cur, t]);

  return (
    <section className="card p-5">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <SectionTitle icon={CloudSun} color="#0891b2">AQI ↔ weather</SectionTitle>
        <div className="inline-flex overflow-hidden rounded-lg border border-border text-xs">
          {WX.map((w) => (
            <button key={w.key} onClick={() => setWx(w.key)} className={`px-3 py-1.5 ${wx === w.key ? "bg-accent text-white" : "text-muted hover:bg-surface-2"}`}>
              {w.label}
            </button>
          ))}
        </div>
      </div>
      <EChart option={option} height={240} ariaLabel="AQI versus weather dual-axis chart" />
    </section>
  );
}
