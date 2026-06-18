import { useMemo } from "react";
import { Sigma } from "lucide-react";
import { SectionTitle } from "./SectionTitle";
import { STANDARDS, type StandardId } from "../lib/standards";
import type { DailyRow } from "../lib/data";
import { EChart } from "./EChart";
import { chartTheme } from "../lib/chartTheme";

export function YearSummary({
  rows,
  standard,
  dark,
}: {
  rows: DailyRow[];
  standard: StandardId;
  dark: boolean;
}) {
  const cfg = STANDARDS[standard];
  const t = chartTheme(dark);

  const years = useMemo(() => {
    const by = new Map<string, number[]>();
    for (const r of rows) {
      let v = cfg.numeric ? (standard === "naqi" ? r.aqi_naqi : r.aqi_us)
        : (r.eu_band ? cfg.bands.findIndex((b) => b.label === r.eu_band) : null);
      if (v == null || v < 0) continue; // -1 = unknown band label; skip rather than crash later
      const yr = r.date.slice(0, 4);
      (by.get(yr) ?? by.set(yr, []).get(yr)!).push(v);
    }
    const poorCut = cfg.numeric ? (standard === "naqi" ? 200 : 150) : 3; // Poor+ band index 3
    return [...by.entries()].sort().map(([yr, vs]) => {
      const avg = Math.round(vs.reduce((a, b) => a + b, 0) / vs.length);
      const peak = Math.max(...vs);
      const good = vs.filter((v) => (cfg.numeric ? v <= 50 : v <= 1)).length;
      const poor = vs.filter((v) => v > poorCut || (!cfg.numeric && v >= poorCut)).length;
      return { yr, avg, peak, good, poor, n: vs.length };
    });
  }, [rows, standard, cfg]);
  if (years.length === 0) return null;
  const option = {
  grid: { left: 44, right: 16, top: 16, bottom: 28 },

  tooltip: {
    trigger: "axis",
    backgroundColor: t.tooltipBg,
    borderWidth: 0,
    textStyle: { color: t.ink, fontSize: 12 },
  },
legend: {
  top: 0,
  textStyle: {
    color: t.label,
  },
},
  xAxis: {
    type: "category",
    data: years.map((y) => y.yr),
    axisLine: { lineStyle: { color: t.axis } },
    axisLabel: { color: t.label, fontSize: 11 },
  },

  yAxis: {
    type: "value",
    axisLabel: { color: t.label, fontSize: 11 },
    splitLine: { lineStyle: { color: t.split } },
  },

series: [
  {
    name: "Average AQI",
    type: "line",
    data: years.map((y) => y.avg),
    smooth: true,
    lineStyle: {
      color: cfg.bands[1].color,
      width: 2,
    },
    itemStyle: {
      color: cfg.bands[1].color,
    },
  },
  {
    name: "Peak AQI",
    type: "line",
    data: years.map((y) => y.peak),
    smooth: true,
    lineStyle: {
      color: cfg.bands[3].color,
      width: 2,
    },
    itemStyle: {
      color: cfg.bands[3].color,
    },
  },
],
};

  return (
    <section className="card p-5">
      <div className="mb-3"><SectionTitle icon={Sigma} color="#0d9488" eyebrow="Annual summary" info="Per-year average and peak AQI, plus how many days fell in each band.">Year-by-year</SectionTitle></div>
<EChart
  option={option}
  height={280}
  ariaLabel="Year-by-year AQI summary chart"
/>
    </section>
  );
}
