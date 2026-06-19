import { useMemo } from "react";
import { Sigma } from "lucide-react";
import { SectionTitle } from "./SectionTitle";
import type { DailyRow } from "../lib/data";
import { EChart } from "./EChart";
import { chartTheme } from "../lib/chartTheme";
import { STANDARDS, bandForIndex, type StandardId } from "../lib/standards";
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
  const avgColor = cfg.numeric
  ? bandForIndex(
      standard,
      Math.round(
        years.reduce((s, y) => s + y.avg, 0) / years.length
      )
    ).color
  : cfg.bands[1].color;

const peakColorSeries = cfg.numeric
  ? bandForIndex(
      standard,
      Math.max(...years.map((y) => y.peak))
    ).color
  : cfg.bands[3].color;
  const option = {
  grid: { left: 44, right: 16, top: 16, bottom: 28 },

tooltip: {
  trigger: "axis",
  backgroundColor: t.tooltipBg,
  borderWidth: 0,
  textStyle: { color: t.ink, fontSize: 12 },

  formatter: (params: any) => {
    const year = years[params[0].dataIndex];

    return `
      <strong>${year.yr}</strong><br/>
      Average AQI: ${year.avg}<br/>
      Peak AQI: ${year.peak}<br/>
      Good Days: ${year.good}<br/>
      Poor Days: ${year.poor}<br/>
      Total Days: ${year.n}
    `;
  },
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
      color: avgColor,
      width: 2,
    },
    itemStyle: {
      color: avgColor,
    },
  },
  {
    name: "Peak AQI",
    type: "line",
    data: years.map((y) => y.peak),
    smooth: true,
    lineStyle: {
  color: peakColorSeries,
  width: 2,
},
itemStyle: {
  color: peakColorSeries,
},
  },
],
};

return (
  <section className="card p-5">
    <div className="mb-3">
      <SectionTitle
        icon={Sigma}
        color="#0d9488"
        eyebrow="Annual summary"
        info="Annual AQI trends and per-year summary statistics."
      >
        Year-by-year
      </SectionTitle>
    </div>

    {standard !== "eu" && (
      <EChart
        option={option}
        height={280}
        ariaLabel="Year-by-year AQI summary chart"
      />
    )}

    <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
      {years.map((y) => {
        const peakColor = cfg.numeric
          ? bandForIndex(standard, y.peak).color
          : cfg.bands[Math.min(5, y.peak)].color;

        return (
          <div
            key={y.yr}
            className="rounded-lg border border-border bg-bg-soft/40 p-3"
          >
            <div className="font-display text-lg text-heading">
              {y.yr}
            </div>

            <div className="mt-1 flex items-baseline justify-between text-sm">
              <span className="text-body">avg</span>
              <span className="font-medium text-heading">
                {y.avg}
              </span>
            </div>

            <div className="flex items-baseline justify-between text-sm">
              <span className="text-body">peak</span>
              <span
                className="font-medium"
                style={{ color: peakColor }}
              >
                {y.peak}
              </span>
            </div>

            <div className="mt-1 flex justify-between text-xs text-muted">
              <span>{y.good} good</span>
              <span>{y.poor} poor</span>
            </div>

            <div className="mt-1 text-xs text-muted">
              {y.n} days
            </div>
          </div>
        );
      })}
    </div>
  </section>
);
}
