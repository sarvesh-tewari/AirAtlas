import { useEffect, useMemo, useState } from "react";
import type { EChartsCoreOption } from "echarts";
import { CalendarRange } from "lucide-react";
import { EChart, chartTheme } from "./EChart";
import { SectionTitle } from "./SectionTitle";
import { STANDARDS, bandForIndex, type StandardId } from "../lib/standards";
import type { DailyRow } from "../lib/data";

export function Exceedance({ rows, standard, dark }: { rows: DailyRow[]; standard: StandardId; dark: boolean }) {
  const t = chartTheme(dark);
  const cfg = STANDARDS[standard];

  // Standard-aware thresholds.
  const thresholds = cfg.numeric ? (standard === "naqi" ? [50, 100, 200, 300] : [50, 100, 150, 200]) : [2, 3, 4];
  const [thr, setThr] = useState(thresholds[1]);
  // Thresholds differ per standard (EU uses band indices) — reset when the standard changes
  // so a carried-over numeric threshold isn't used as an out-of-range EU band index.
  useEffect(() => {
    setThr(cfg.numeric ? (standard === "naqi" ? 100 : 100) : 3);
  }, [standard, cfg.numeric]);

  const { years, counts, color } = useMemo(() => {
    const byYear = new Map<string, number>();
    for (const r of rows) {
      const yr = r.date.slice(0, 4);
      let exceed = false;
      if (cfg.numeric) {
        const v = standard === "naqi" ? r.aqi_naqi : r.aqi_us;
        exceed = v != null && v > thr;
      } else {
        const rank = r.eu_band ? cfg.bands.findIndex((b) => b.label === r.eu_band) : -1;
        exceed = rank >= thr;
      }
      if (!byYear.has(yr)) byYear.set(yr, 0);
      if (exceed) byYear.set(yr, byYear.get(yr)! + 1);
    }
    const ys = [...byYear.keys()].sort();
    const col = cfg.numeric ? bandForIndex(standard, thr + 1).color : cfg.bands[thr].color;
    return { years: ys, counts: ys.map((y) => byYear.get(y)!), color: col };
  }, [rows, standard, thr, cfg]);

  const option = useMemo(() => ({
    grid: { left: 36, right: 12, top: 12, bottom: 24 },
    tooltip: { trigger: "axis", backgroundColor: t.tooltipBg, borderWidth: 0, textStyle: { color: t.ink, fontSize: 12 } },
    xAxis: { type: "category", data: years, axisLine: { lineStyle: { color: t.axis } }, axisLabel: { color: t.label, fontSize: 11 } },
    yAxis: { type: "value", name: "days", nameTextStyle: { color: t.label, fontSize: 10 }, axisLabel: { color: t.label, fontSize: 11 }, splitLine: { lineStyle: { color: t.split } } },
    series: [{ type: "bar", data: counts, itemStyle: { color, borderRadius: [4, 4, 0, 0] }, barMaxWidth: 48 }],
  } as EChartsCoreOption), [years, counts, color, t]);

  const label = (v: number) => (cfg.numeric ? `> ${v}` : `${cfg.bands[v].label}+`);

  return (
    <section className="card p-5">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <SectionTitle icon={CalendarRange}>Exceedance — bad-air days per year</SectionTitle>
        <div className="inline-flex overflow-hidden rounded-lg border border-border text-xs">
          {thresholds.map((v) => (
            <button key={v} onClick={() => setThr(v)} className={`px-3 py-1.5 ${thr === v ? "bg-accent text-white" : "text-muted hover:bg-surface-2"}`}>
              {label(v)}
            </button>
          ))}
        </div>
      </div>
      {years.length ? <EChart option={option} height={220} /> : <p className="py-8 text-center text-sm text-muted">No data.</p>}
      <p className="mt-2 text-xs text-faint">Days where daily AQI exceeds {label(thr)} ({cfg.name}).</p>
    </section>
  );
}
