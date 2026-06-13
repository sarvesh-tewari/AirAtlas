import { useMemo } from "react";
import type { EChartsCoreOption } from "echarts";
import { CalendarRange } from "lucide-react";
import { EChart } from "./EChart";
import { chartTheme } from "../lib/chartTheme";
import { SectionTitle } from "./SectionTitle";
import { STANDARDS, bandForIndex, type StandardId } from "../lib/standards";
import type { DailyRow } from "../lib/data";

// How many days fell in each AQI category, per year (stacked). Non-cumulative and intuitive:
// each day is counted once, in exactly one band.
export function Exceedance({ rows, standard, dark }: { rows: DailyRow[]; standard: StandardId; dark: boolean }) {
  const t = chartTheme(dark);
  const cfg = STANDARDS[standard];

  const { years, perBand } = useMemo(() => {
    const counts = new Map<string, number[]>(); // year -> [count per band index]
    for (const r of rows) {
      let bandIdx: number;
      if (cfg.numeric) {
        const v = standard === "naqi" ? r.aqi_naqi : r.aqi_us;
        if (v == null) continue;
        bandIdx = cfg.bands.indexOf(bandForIndex(standard, v));
      } else {
        if (!r.eu_band) continue;
        bandIdx = cfg.bands.findIndex((b) => b.label === r.eu_band);
      }
      if (bandIdx < 0) continue; // unknown band label - don't write counts[-1]
      const yr = r.date.slice(0, 4);
      if (!counts.has(yr)) counts.set(yr, new Array(cfg.bands.length).fill(0));
      counts.get(yr)![bandIdx] += 1;
    }
    const ys = [...counts.keys()].sort();
    const pb = cfg.bands.map((_, i) => ys.map((y) => counts.get(y)![i]));
    return { years: ys, perBand: pb };
  }, [rows, standard, cfg]);

  const option = useMemo(() => ({
    grid: { left: 40, right: 12, top: 8, bottom: 48 },
    legend: { bottom: 0, textStyle: { color: t.label, fontSize: 10 }, itemWidth: 10, itemHeight: 10 },
    tooltip: { trigger: "axis", axisPointer: { type: "shadow" }, backgroundColor: t.tooltipBg, borderWidth: 0, textStyle: { color: t.ink, fontSize: 12 } },
    xAxis: { type: "category", data: years, axisLine: { lineStyle: { color: t.axis } }, axisLabel: { color: t.label, fontSize: 11 } },
    yAxis: { type: "value", name: "days", nameTextStyle: { color: t.label, fontSize: 10 }, axisLabel: { color: t.label, fontSize: 11 }, splitLine: { lineStyle: { color: t.split } } },
    series: cfg.bands.map((b, i) => ({
      name: b.label, type: "bar", stack: "days", data: perBand[i],
      itemStyle: { color: b.color }, barMaxWidth: 48,
    })),
  } as EChartsCoreOption), [years, perBand, cfg, t]);

  return (
    <section className="card p-5">
      <div className="mb-3"><SectionTitle icon={CalendarRange} color="#d97706" eyebrow="Clean-air days">Days by air-quality band</SectionTitle></div>
      {years.length ? <EChart option={option} height={260} ariaLabel="Stacked count of days in each AQI band per year" /> : <p className="py-8 text-center text-sm text-body">No data.</p>}
      <p className="mt-2 text-xs text-muted">Each day counted once in its {cfg.name} band. Hover a year for the breakdown.</p>
    </section>
  );
}
