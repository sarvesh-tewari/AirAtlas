import { useMemo } from "react";
import type { EChartsCoreOption } from "echarts";
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

  const years = useMemo(() => {
    const by = new Map<string, number[]>();
    for (const r of rows) {
      let v = cfg.numeric
        ? standard === "naqi"
          ? r.aqi_naqi
          : r.aqi_us
        : r.eu_band
          ? cfg.bands.findIndex((b) => b.label === r.eu_band)
          : null;
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

  const fmt = (v: number) => (cfg.numeric ? `${v}` : (cfg.bands[v]?.label ?? `${v}`));

  // EU has no numeric AQI, so (like the multi-year TrendChart) we plot the band index on a
  // 0..6 axis and label the ticks with band names rather than numbers. The lines use neutral
  // theme colours; the y-axis carries the category meaning.
  const option = useMemo(() => {
    const t = chartTheme(dark);
    const yAxis = cfg.numeric
      ? {
          type: "value",
          axisLabel: { color: t.label, fontSize: 11 },
          splitLine: { lineStyle: { color: t.split } },
        }
      : {
          type: "value",
          min: 0,
          max: 6,
          interval: 1,
          axisLabel: {
            color: t.label,
            fontSize: 10,
            formatter: (v: number) => cfg.bands[v]?.label ?? "",
          },
          splitLine: { lineStyle: { color: t.split } },
        };
    const line = (name: string, key: "avg" | "peak", color: string) => ({
      name,
      type: "line",
      data: years.map((y) => y[key]),
      smooth: true,
      lineStyle: { color, width: 2 },
      itemStyle: { color },
    });
    return {
      // EU band names ("Extremely Poor") need more room than numeric AQI tick labels.
      grid: { left: cfg.numeric ? 44 : 92, right: 16, top: 28, bottom: 28 },
      legend: { top: 0, textStyle: { color: t.label } },
      tooltip: {
        trigger: "axis",
        backgroundColor: t.tooltipBg,
        borderWidth: 0,
        textStyle: { color: t.ink, fontSize: 12 },
        formatter: (params: any) => {
          const y = years[params[0].dataIndex];
          return `<strong>${y.yr}</strong><br/>Average: ${fmt(y.avg)}<br/>Peak: ${fmt(y.peak)}<br/>${y.good} good days, ${y.poor} poor days<br/>${y.n} days total`;
        },
      },
      xAxis: {
        type: "category",
        data: years.map((y) => y.yr),
        axisLine: { lineStyle: { color: t.axis } },
        axisLabel: { color: t.label, fontSize: 11 },
      },
      yAxis,
      series: [line("Average", "avg", t.ink), line("Peak", "peak", t.accent)],
      // fmt is pure over cfg (in deps), so referencing it here is safe.
    } as EChartsCoreOption;
  }, [years, dark, cfg]);

  return (
    <section className="card p-5">
      <div className="mb-3">
        <SectionTitle
          icon={Sigma}
          color="#0d9488"
          eyebrow="Annual summary"
          info="Each year's average and peak air quality, plus how many days were good or poor."
        >
          Year-by-year
        </SectionTitle>
      </div>

      <EChart option={option} height={280} ariaLabel="Year-by-year air quality summary chart" />

      <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
        {years.map((y) => {
          const peakColor = cfg.numeric
            ? bandForIndex(standard, y.peak).color
            : (cfg.bands[y.peak]?.color ?? cfg.bands[0].color);

          return (
            <div key={y.yr} className="rounded-lg border border-border bg-bg-soft/40 p-3">
              <div className="font-display text-lg text-heading">{y.yr}</div>

              <div className="mt-1 flex items-baseline justify-between text-sm">
                <span className="text-body">avg</span>
                <span className="font-medium text-heading">{fmt(y.avg)}</span>
              </div>

              <div className="flex items-baseline justify-between text-sm">
                <span className="text-body">peak</span>
                <span className="font-medium" style={{ color: peakColor }}>
                  {fmt(y.peak)}
                </span>
              </div>

              <div className="mt-1 flex justify-between text-xs text-muted">
                <span>{y.good} good</span>
                <span>{y.poor} poor</span>
              </div>

              <div className="mt-1 text-xs text-muted">{y.n} days</div>
            </div>
          );
        })}
      </div>
    </section>
  );
}
