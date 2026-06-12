import { useMemo, useState } from "react";
import type { EChartsCoreOption } from "echarts";
import { EChart, chartTheme } from "./EChart";
import { STANDARDS, type StandardId } from "../lib/standards";
import type { DailyRow } from "../lib/data";

type Range = "90d" | "1y" | "all";

export function TrendChart({ rows, standard, dark }: { rows: DailyRow[]; standard: StandardId; dark: boolean }) {
  const [range, setRange] = useState<Range>("1y");
  const cfg = STANDARDS[standard];
  const t = chartTheme(dark);

  const filtered = useMemo(() => {
    if (!rows.length || range === "all") return rows;
    const last = new Date(rows[rows.length - 1].date).getTime();
    const days = range === "90d" ? 90 : 365;
    const cut = last - days * 864e5;
    return rows.filter((r) => new Date(r.date).getTime() >= cut);
  }, [rows, range]);

  const option = useMemo(() => {
    const numeric = cfg.numeric;
    const data: [string, number | null][] = filtered.map((r) => {
      let v: number | null;
      if (standard === "naqi") v = r.aqi_naqi;
      else if (standard === "us") v = r.aqi_us;
      else v = r.eu_band ? cfg.bands.findIndex((b) => b.label === r.eu_band) : null;
      return [r.date, v];
    });

    // Horizontal category bands behind the line.
    let lo = 0;
    const bandAreas = cfg.bands.map((b, i) => {
      const hi = numeric ? (b.max ?? cfg.max) : i + 1;
      const area = [{ yAxis: numeric ? lo : i, itemStyle: { color: b.color + (dark ? "26" : "1f") } }, { yAxis: hi }];
      lo = hi;
      return area;
    });

    // Today/history seam: first row tagged cpcb.
    const seamRow = filtered.find((r) => r.source === "cpcb");

    return {
      grid: { left: 44, right: 16, top: 16, bottom: 28 },
      tooltip: { trigger: "axis", backgroundColor: t.tooltipBg, borderWidth: 0,
        textStyle: { color: t.ink, fontSize: 12 } },
      xAxis: { type: "time", axisLine: { lineStyle: { color: t.axis } },
        axisLabel: { color: t.label, fontSize: 11 }, splitLine: { show: false } },
      yAxis: numeric
        ? { type: "value", min: 0, max: cfg.max, axisLabel: { color: t.label, fontSize: 11 },
            splitLine: { lineStyle: { color: t.split } } }
        : { type: "value", min: 0, max: 6, interval: 1,
            axisLabel: { color: t.label, fontSize: 10,
              formatter: (v: number) => cfg.bands[v]?.label ?? "" },
            splitLine: { lineStyle: { color: t.split } } },
      series: [{
        type: "line", data, showSymbol: false, smooth: false,
        lineStyle: { color: t.ink, width: 1.5 }, connectNulls: false,
        z: 3,
        markArea: { silent: true, data: bandAreas as unknown as object[] },
        markLine: seamRow
          ? { symbol: "none", silent: true,
              data: [{ xAxis: seamRow.date, label: { formatter: "today (CPCB)", color: t.label, fontSize: 10 },
                lineStyle: { color: t.accent, type: "dashed" } }] }
          : undefined,
      }],
    } as EChartsCoreOption;
  }, [filtered, standard, dark, cfg, t]);

  return (
    <section className="card p-5">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="font-display text-lg text-ink">Multi-year trend</h2>
        <div className="inline-flex overflow-hidden rounded-lg border border-border text-xs">
          {(["90d", "1y", "all"] as Range[]).map((r) => (
            <button
              key={r}
              onClick={() => setRange(r)}
              className={`px-3 py-1.5 ${range === r ? "bg-accent text-white" : "text-muted hover:bg-surface-2"}`}
            >
              {r === "90d" ? "90 days" : r === "1y" ? "1 year" : "All"}
            </button>
          ))}
        </div>
      </div>
      {filtered.length > 1 ? (
        <EChart option={option} height={260} />
      ) : (
        <p className="py-10 text-center text-sm text-muted">Not enough history for this range.</p>
      )}
    </section>
  );
}
